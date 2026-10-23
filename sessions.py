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
    RECOVERY_LIFETIME = 365 * 86400

    def __init__(self, path, max_sessions=32, ttl_seconds=86400, clock=time.time,
                 max_requests_per_minute=600, recovery_key=None):
        self.path = Path(path)
        self.max_sessions = max_sessions
        self.ttl = ttl_seconds
        self.clock = clock
        self.max_requests = max_requests_per_minute
        configured = recovery_key if recovery_key is not None else os.environ.get("DYSON_RECOVERY_KEY", "")
        if configured and not re.fullmatch(r"[0-9a-fA-F]{64}", configured):
            raise ValueError("DYSON_RECOVERY_KEY must be a stable 32-byte hex secret")
        self.recovery_key = bytes.fromhex(configured) if configured else None
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")  # serialize additive migrations across workers
            db.execute("""CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, signing_key TEXT NOT NULL,
                checkpoint TEXT NOT NULL, expires REAL NOT NULL)""")
            # Additive migration preserves the first PR's existing databases.
            columns = {row[1] for row in db.execute("PRAGMA table_info(sessions)")}
            if "recovery_owner" not in columns:
                db.execute("ALTER TABLE sessions ADD COLUMN recovery_owner TEXT")
            if "saved_at" not in columns:
                db.execute("ALTER TABLE sessions ADD COLUMN saved_at REAL NOT NULL DEFAULT 0")
            if "revision" not in columns:
                db.execute("ALTER TABLE sessions ADD COLUMN revision INTEGER NOT NULL DEFAULT 0")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS recovery_owner ON sessions(recovery_owner)")
            db.execute("""CREATE TABLE IF NOT EXISTS request_limits (
                id TEXT PRIMARY KEY, window_start REAL NOT NULL, requests INTEGER NOT NULL)""")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def recovery_capsule(self, checkpoint, owner, issued, revision):
        capsule = {"format": "dyson-recovery-v1", "owner": owner, "issued_at": issued, "revision": revision,
                   "expires_at": issued + self.RECOVERY_LIFETIME, "checkpoint": checkpoint}
        signature = hmac.new(self.recovery_key, b"dyson-recovery-v1\0" + signing_bytes(capsule),
                             hashlib.sha256).hexdigest()
        return {**capsule, "signature": signature}

    def verify_recovery(self, capsule, credential):
        if not self.recovery_key:
            raise SessionError(503, "Redeploy recovery requires a stable hosting recovery key")
        signed = dict(capsule)
        signature = signed.pop("signature", "")
        if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature):
            raise SessionError(403, "Invalid recovery backup")
        expected = hmac.new(self.recovery_key, b"dyson-recovery-v1\0" + signing_bytes(signed),
                            hashlib.sha256).hexdigest()
        if (not hmac.compare_digest(signature, expected)
                or signed.get("format") != "dyson-recovery-v1"
                or signed.get("owner") != hashlib.sha256(credential.encode()).hexdigest()):
            raise SessionError(403, "Recovery backup or ownership proof is invalid")
        if signed["expires_at"] <= self.clock():
            raise SessionError(410, "Recovery backup expired")
        checkpoint = signed["checkpoint"]
        if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("bodies"), list):
            raise SessionError(422, "Invalid recovery checkpoint")
        if len(checkpoint["bodies"]) > MAX_BODIES:
            raise SessionError(413, "Body limit exceeded")
        return checkpoint, signed["issued_at"], signed["revision"]

    def run(self, token, operation, recovery_token=None, recovery_capsule=None):
        """Atomic world update, optionally bootstrapping from a client backup.

        Recovery verifies both server provenance and an independent browser-held
        credential, never trusting an uploaded world or another owner's cookie.
        A surviving live row wins over an older backup, so retries cannot rewind it.
        """
        recovering = recovery_capsule is not None
        if recovery_token is not None and not TOKEN_PATTERN.fullmatch(recovery_token):
            raise SessionError(401, "Invalid recovery credential")
        if recovering and recovery_token is None:
            raise SessionError(401, "Recovery credential required")
        owner = hashlib.sha256(recovery_token.encode()).hexdigest() if recovery_token else None
        if recovering:
            checkpoint, issued, revision = self.verify_recovery(recovery_capsule, recovery_token)
        elif token is not None and not TOKEN_PATTERN.fullmatch(token):
            raise SessionError(401, "Invalid session credential")
        db = None
        try:
            db = self.connect()
            db.execute("BEGIN IMMEDIATE")
            now = self.clock()
            db.execute("DELETE FROM sessions WHERE expires <= ?", (now,))
            db.execute("DELETE FROM request_limits WHERE id NOT IN (SELECT id FROM sessions)")
            row = None
            old_sid = None
            if recovering:
                row = db.execute("SELECT id, signing_key, checkpoint, recovery_owner, saved_at, revision FROM sessions WHERE recovery_owner=?",
                                 (owner,)).fetchone()
            elif token is not None:
                sid = hashlib.sha256(token.encode()).hexdigest()
                row = db.execute("SELECT id, signing_key, checkpoint, recovery_owner, saved_at, revision FROM sessions WHERE id=?",
                                 (sid,)).fetchone()
                if row is None:
                    raise SessionError(401, "Session expired or unavailable; recover your browser backup")
            if row is not None:
                old_sid, key, saved, bound_owner, saved_at, revision = row
                if owner is not None and bound_owner is not None and owner != bound_owner:
                    raise SessionError(403, "Browser backup belongs to a different session")
                owner = bound_owner or owner
                world = CloudWorld(0)
                world.restore(json.loads(saved))
            else:
                if db.execute("SELECT count(*) FROM sessions").fetchone()[0] >= self.max_sessions:
                    raise SessionError(429, "Session capacity reached; retry after sessions expire")
                key = secrets.token_hex(32)
                if recovering:
                    world = CloudWorld(0)
                    world.restore(checkpoint)
                    saved, saved_at = encode(world.checkpoint()), issued
                else:
                    world, saved, saved_at, revision = CloudWorld(), None, now, 0
            # A missing cookie may not create a duplicate of an already bound world.
            if owner and not recovering and db.execute(
                    "SELECT 1 FROM sessions WHERE recovery_owner=? AND id!=?", (owner, old_sid or "")).fetchone():
                raise SessionError(401, "Browser backup already bound; use recovery")
            if recovering or token is None:
                token = secrets.token_urlsafe(32)
            sid = hashlib.sha256(token.encode()).hexdigest()
            quota = db.execute("SELECT window_start, requests FROM request_limits WHERE id=?", (old_sid or sid,)).fetchone()
            window, requests = quota if quota and now - quota[0] < 60 else (now, 0)
            if requests >= self.max_requests:
                raise SessionError(429, "Session request limit reached; retry in one minute")
            result = operation(world, sid, key, now)
            current = encode(world.checkpoint())
            if len(current.encode()) > MAX_CHECKPOINT_BYTES:
                raise SessionError(413, "Checkpoint exceeds storage limit")
            if current != saved:
                revision += 1
            if current != saved or saved_at <= 0 or now - saved_at > 86400:
                saved_at = now
            if old_sid is not None and old_sid != sid:
                db.execute("DELETE FROM sessions WHERE id=?", (old_sid,))
                db.execute("DELETE FROM request_limits WHERE id=?", (old_sid,))
            db.execute("""INSERT OR REPLACE INTO sessions
                       (id, signing_key, checkpoint, expires, recovery_owner, saved_at, revision) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                       (sid, key, current, now + self.ttl, owner, saved_at, revision))
            db.execute("INSERT OR REPLACE INTO request_limits VALUES (?, ?, ?)",
                       (sid, window, requests + 1))
            if isinstance(result, dict) and "engine" in result:
                result["recovery"] = (self.recovery_capsule(world.checkpoint(), owner, saved_at, revision)
                                      if self.recovery_key and owner else None)
            db.commit()
            return result, token, row is None
        except sqlite3.DatabaseError as exc:
            raise SessionError(503, "Session storage busy or unavailable; retry") from exc
        finally:
            if db is not None:
                db.close()

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
