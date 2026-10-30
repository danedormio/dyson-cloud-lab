"""Isolate persistent data and support both CI Chromium and installed Chromium."""
from contextlib import contextmanager
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def isolated_sessions(app, store):
    # State stores dynamic attributes outside __dict__. pytest 9.2's setattr
    # undo deletes such an attribute instead of restoring its original value.
    # Read first so a missing application initialization still fails loudly.
    original = app.state.sessions
    app.state.sessions = store
    try:
        yield
    finally:
        app.state.sessions = original


@pytest.fixture(autouse=True)
def isolated_api(tmp_path):
    from server import app
    from sessions import SessionStore
    with isolated_sessions(app, SessionStore(tmp_path / "sessions.sqlite3")):
        yield


class Backend:
    def __init__(self, tmp_path):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.db = tmp_path / "browser-sessions.sqlite3"
        self.logs = tmp_path / "backend.log"
        self.proc = None
        self.recovery_key = secrets.token_hex(32)

    def start(self):
        env = {**os.environ, "DYSON_SESSION_DB": str(self.db), "DYSON_RECOVERY_KEY": self.recovery_key or ""}
        self.log = self.logs.open("ab")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=ROOT, env=env, stdout=self.log, stderr=self.log)
        for _ in range(100):
            if self.proc.poll() is not None:
                raise AssertionError(self.logs.read_text())
            try:
                with urllib.request.urlopen(self.url + "/health", timeout=1) as r:
                    assert r.status == 200
                return
            except OSError:
                time.sleep(0.1)
        raise AssertionError("Backend readiness timeout: " + self.logs.read_text())

    def stop(self, crash=False):
        if self.proc is not None:
            self.proc.kill() if crash else self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
            self.proc = None
            self.log.close()


@pytest.fixture
def backend(tmp_path):
    backend = Backend(tmp_path)
    try:
        backend.start()
        yield backend
    finally:
        backend.stop()


@pytest.fixture
def chromium():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        options = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if os.environ.get("DYSON_CHROMIUM_EXECUTABLE"):
            options["executable_path"] = os.environ["DYSON_CHROMIUM_EXECUTABLE"]
        browser = p.chromium.launch(**options)
        yield browser
        browser.close()
