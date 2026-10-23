"""Session-isolated REBOUND service. Production deployment remains approval-gated."""
import json
import os
from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ConfigDict
from starlette.datastructures import Headers

from sessions import (SessionStore, SessionError, COOKIE_NAME, MAX_BODIES,
                      MAX_CHECKPOINT_BYTES)


class BoundedAPI:
    """Reject oversized bodies before JSON parsing, including chunked uploads."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        if headers.get("sec-fetch-site") == "cross-site":
            return await JSONResponse({"detail": "Cross-site API request rejected"}, 403)(scope, receive, send)
        if scope["method"] not in ("GET", "HEAD"):
            origin = headers.get("origin")
            expected = f'{scope["scheme"]}://{headers.get("host")}'
            if origin and origin != expected:
                return await JSONResponse({"detail": "Cross-origin mutation rejected"}, 403)(scope, receive, send)
            if headers.get("content-type", "").split(";")[0] != "application/json":
                return await JSONResponse({"detail": "Use application/json"}, 415)(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > MAX_CHECKPOINT_BYTES:
                return await JSONResponse({"detail": "Request exceeds checkpoint size limit"}, 413)(scope, receive, send)
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        if body:
            try:
                def invalid_constant(value):
                    raise ValueError("Non-finite JSON")
                json.loads(body, parse_constant=invalid_constant)
            except (ValueError, RecursionError):
                return await JSONResponse({"detail": "Malformed or non-finite JSON"}, 422)(scope, receive, send)
        async def replay():
            return {"type": "http.request", "body": body, "more_body": False}
        async def private_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message["headers"]) + [(b"cache-control", b"no-store")]
            await send(message)
        await self.app(scope, replay, private_send)


class InputModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")


class StepRequest(InputModel):
    seconds: float = Field(default=3600, gt=0, le=2_592_000)


class LaunchRequest(InputModel):
    speed_kms: float = Field(default=25, gt=0, le=100_000)
    impact_au: float = Field(default=0.5, ge=-25, le=25)
    offset_degrees: float = Field(default=0, ge=-180, le=180)


class ResetRequest(InputModel):
    cloud_count: int = Field(default=72, ge=0, le=MAX_BODIES - 2)


class SessionRequest(InputModel):
    recovery_token: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{43}$")
    has_backup: bool = False


class RecoveryRequest(InputModel):
    credential: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    capsule: dict


def create_app(store=None):
    app = FastAPI(title="Dyson Cloud Laboratory — REBOUND sessions")
    app.state.sessions = store or SessionStore(os.environ.get(
        "DYSON_SESSION_DB", str(Path(__file__).parent / ".session-data" / "sessions.sqlite3")))
    app.add_middleware(BoundedAPI)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Never echo submitted checkpoints, bearer credentials, or NaN/Infinity
        # through error serialization (non-finite JSON otherwise yields a 500).
        return JSONResponse({"detail": "Invalid request fields or JSON"}, 422)

    def run(request, response, operation, **recovery):
        try:
            result, token, _ = app.state.sessions.run(request.cookies.get(COOKIE_NAME), operation, **recovery)
        except SessionError as exc:
            raise HTTPException(exc.status, exc.message) from exc
        except (ValueError, OverflowError, RecursionError) as exc:
            raise HTTPException(422, "Invalid simulation request") from exc
        # Refresh browser expiry alongside the server's sliding inactivity TTL.
        response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="strict",
                            secure=request.url.scheme == "https", path="/api",
                            max_age=int(app.state.sessions.ttl))
        return result

    @app.get("/health")
    def health():
        try:
            with app.state.sessions.connect() as db:
                db.execute("SELECT count(*) FROM sessions").fetchone()
        except sqlite3.Error as exc:
            raise HTTPException(503, "Session storage unavailable") from exc
        return {"status": "ok", "engine": "REBOUND IAS15",
                "recovery_available": bool(app.state.sessions.recovery_key)}

    @app.get("/api/state")
    def state(request: Request, response: Response):
        return run(request, response, lambda w, *_: w.state())

    @app.post("/api/session")
    def bootstrap(payload: SessionRequest, request: Request, response: Response):
        if payload.has_backup and not request.cookies.get(COOKIE_NAME):
            raise HTTPException(401, "Resume the saved browser backup")
        return run(request, response, lambda w, *_: w.state(), recovery_token=payload.recovery_token)

    @app.post("/api/recover")
    def recover(payload: RecoveryRequest, request: Request, response: Response):
        return run(request, response, lambda w, *_: w.state(),
                   recovery_token=payload.credential, recovery_capsule=payload.capsule)

    @app.delete("/api/session")
    def forget(response: Response):
        # Forget only this browser's credential; old storage expires naturally.
        response.delete_cookie(COOKIE_NAME, path="/api", httponly=True, samesite="strict")
        return {"status": "forgotten"}

    @app.post("/api/step")
    def step(payload: StepRequest, request: Request, response: Response):
        return run(request, response, lambda w, *_: w.step(payload.seconds))

    @app.post("/api/launch")
    def launch(payload: LaunchRequest, request: Request, response: Response):
        def apply(w, *_):
            if len(w.sim.particles) >= MAX_BODIES:
                raise SessionError(409, "Body limit reached; reset with fewer cloud bodies")
            return w.add_incoming(payload.speed_kms, payload.impact_au, payload.offset_degrees)
        return run(request, response, apply)

    @app.post("/api/reset")
    def reset(payload: ResetRequest, request: Request, response: Response):
        return run(request, response, lambda w, *_: w.reset(payload.cloud_count))

    @app.get("/api/checkpoint")
    def checkpoint(request: Request, response: Response):
        return run(request, response, app.state.sessions.export)

    @app.post("/api/restore")
    def restore(payload: dict, request: Request, response: Response):
        return run(request, response, lambda w, sid, key, now:
                   app.state.sessions.restore(w, payload, sid, key, now))

    @app.get("/")
    def browser_frontend():
        return FileResponse(Path(__file__).with_name("rebound.html"))

    @app.get("/recovery.js")
    def recovery_client():
        return FileResponse(Path(__file__).with_name("recovery.js"), media_type="text/javascript",
                            headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
