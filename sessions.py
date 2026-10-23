"""Bounded, transactional session storage; no process-global physical universe."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

from physics import CloudWorld

MAX_BODIES = 202
MAX_CHECKPOINT_BYTES = 262_144
COOKIE_NAME = "dyson_session"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")


class SessionError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def signing_bytes(value):
    # JSON.parse/stringify in browsers turns 0.0 into 0 and may render large
    # integral floats without an exponent. Authenticate numerical values rather
    # than Python's original int/float spelling. All scenario numbers are IEEE
    # doubles; non-finite values are rejected by encode, never signed.
    def normalize(item):
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            return float(item)
        if isinstance(item, list):
            return [normalize(x) for x in item]
        if isinstance(item, dict):
            return {k: normalize(v) for k, v in item.items()}
        return item
    return encode(normalize(value)).encode()


class SessionStore:
    def __init__(self, path, max_sessions=32, ttl_seconds=86400, clock=time.time,
                 max_requests_per_minute=600):
        self.path = Path(path)
        self.max_sessions = max_sessions
        self.ttl = ttl_seconds
        self.clock = clock
        self.max_requests = max_requests_per_minute
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, signing_key TEXT NOT NULL,
                checkpoint TEXT NOT NULL, expires REAL NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS request_limits (
                id TEXT PRIMARY KEY, window_start REAL NOT NULL, requests INTEGER NOT NULL)""")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def run(self, token, operation):
        """Load, operate, persist and acknowledge as one cross-worker transaction.

        Only one bounded world is reconstructed at a time per database. Failed
        validation/integration/commit cannot replace the last committed state.
        """
        if token is not None and not TOKEN_PATTERN.fullmatch(token):
            raise SessionError(401, "Invalid session credential")
        db = None
        try:
            db = self.connect()
            db.execute("BEGIN IMMEDIATE")
            now = self.clock()
            db.execute("DELETE FROM sessions WHERE expires <= ?", (now,))
            db.execute("DELETE FROM request_limits WHERE id NOT IN (SELECT id FROM sessions)")
            created = token is None
            if created:
                if db.execute("SELECT count(*) FROM sessions").fetchone()[0] >= self.max_sessions:
                    raise SessionError(429, "Session capacity reached; retry after sessions expire")
                token = secrets.token_urlsafe(32)
                sid = hashlib.sha256(token.encode()).hexdigest()
                key = secrets.token_hex(32)
                world = CloudWorld()
            else:
                sid = hashlib.sha256(token.encode()).hexdigest()
                row = db.execute("SELECT signing_key, checkpoint FROM sessions WHERE id=?", (sid,)).fetchone()
                if row is None:
                    raise SessionError(401, "Session expired or unavailable; start a new session explicitly")
                key, saved = row
            quota = db.execute("SELECT window_start, requests FROM request_limits WHERE id=?", (sid,)).fetchone()
            window, requests = quota if quota and now - quota[0] < 60 else (now, 0)
            if requests >= self.max_requests:
                raise SessionError(429, "Session request limit reached; retry in one minute")
            if not created:
                world = CloudWorld(0)
                world.restore(json.loads(saved))
            result = operation(world, sid, key, now)
            saved = encode(world.checkpoint())
            if len(saved.encode()) > MAX_CHECKPOINT_BYTES:
                raise SessionError(413, "Checkpoint exceeds storage limit")
            db.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?, ?)",
                       (sid, key, saved, now + self.ttl))
            db.execute("INSERT OR REPLACE INTO request_limits VALUES (?, ?, ?)",
                       (sid, window, requests + 1))
            db.commit()
            return result, token, created
        except sqlite3.DatabaseError as exc:
            raise SessionError(503, "Session storage busy or unavailable; retry") from exc
        finally:
            if db is not None:
                db.close()  # rolls back any uncommitted mutation

    def export(self, world, sid, key, now):
        checkpoint = {**world.checkpoint(), "owner": sid, "expires_at": now + self.ttl}
        signature = hmac.new(bytes.fromhex(key), signing_bytes(checkpoint), hashlib.sha256).hexdigest()
        return {**checkpoint, "signature": signature}

    def restore(self, world, payload, sid, key, now):
        signed = dict(payload)
        signature = signed.pop("signature", "")
        if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature):
            raise SessionError(403, "Checkpoint is not authentic for this session")
        expected = hmac.new(bytes.fromhex(key), signing_bytes(signed), hashlib.sha256).hexdigest()
        if (not hmac.compare_digest(signature, expected)
                or signed.get("owner") != sid):
            raise SessionError(403, "Checkpoint is not authentic for this session")
        if signed.get("expires_at", 0) <= now:
            raise SessionError(410, "Checkpoint expired")
        if len(signed.get("bodies", [])) > MAX_BODIES:
            raise SessionError(413, "Body limit exceeded")
        return world.restore(signed)
