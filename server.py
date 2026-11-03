"""Session-isolated REBOUND service. Production deployment remains approval-gated."""
import json
import os
import re
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
    samples: int = Field(default=1, ge=1, le=32)


class TrajectoryRequest(InputModel):
    body_id: int = Field(ge=0, le=MAX_BODIES-1)


class LaunchRequest(InputModel):
    speed_kms: float = Field(default=25, gt=0, le=300)
    impact_au: float = Field(default=0.5, ge=-25, le=25)
    offset_degrees: float = Field(default=0, ge=-180, le=180)
    mass_kg: float = Field(default=1, gt=0, le=1e24)
    azimuth_deg: float = Field(default=0, ge=-180, le=180)
    elevation_deg: float = Field(default=0, ge=-89, le=89)


class ResetRequest(InputModel):
    cloud_count: int = Field(default=72, ge=0, le=MAX_BODIES - 2)
    cloud_mass_kg: float = Field(default=1, gt=0, le=1e20)
    inner_au: float = Field(default=0.8, ge=0.2, le=19.9)
    outer_au: float = Field(default=4, gt=0.2, le=20)
    inclination_deg: float = Field(default=0, ge=0, le=90)
    geometry: str = Field(default="sphere", pattern="^(sphere|disk)$")


class ReplayRequest(InputModel):
    scenario: ResetRequest
    launch: LaunchRequest


class MinimalLaunch(InputModel):
    speed: float = Field(default=45, ge=5, le=180)
    offset: float = Field(default=.65, ge=-1.5, le=1.5)
    angle: float = Field(default=0, ge=-180, le=180)
    elevation: float = Field(default=0, ge=-90, le=90)
    roll: float = Field(default=0, ge=-180, le=180)
    enabled: bool = True
    days: float = Field(default=2., ge=1/12, le=2.)


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
    # Render supplies the deployed source revision. Never infer it from a
    # mutable checkout, expose arbitrary environment text, or invent a SHA.
    revision = os.environ.get("RENDER_GIT_COMMIT", "")
    revision = revision.lower() if re.fullmatch(r"[0-9a-fA-F]{40}", revision) else "unknown"

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Never echo submitted checkpoints, bearer credentials, or NaN/Infinity
        # through error serialization (non-finite JSON otherwise yields a 500).
        return JSONResponse({"detail": "Invalid request fields or JSON"}, 422)

    def run(request, response, operation, cost=1, cookie_name=COOKIE_NAME, **recovery):
        try:
            result, token, _ = app.state.sessions.run(request.cookies.get(cookie_name), operation, cost=cost, **recovery)
        except SessionError as exc:
            raise HTTPException(exc.status, exc.message) from exc
        except (ValueError, OverflowError, RecursionError) as exc:
            raise HTTPException(422, "Invalid simulation request") from exc
        # Refresh browser expiry alongside the server's sliding inactivity TTL.
        response.set_cookie(cookie_name, token, httponly=True, samesite="strict",
                            secure=request.url.scheme == "https", path="/api",
                            max_age=int(app.state.sessions.ttl))
        return result

    @app.get("/health")
    def health(response: Response):
        try:
            with app.state.sessions.connect() as db:
                db.execute("SELECT count(*) FROM sessions").fetchone()
        except sqlite3.Error as exc:
            raise HTTPException(503, "Session storage unavailable") from exc
        response.headers["Cache-Control"] = "no-store"
        return {"status": "ok", "engine": "REBOUND IAS15", "revision": revision,
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
        return run(request, response, lambda w, *_: w.step(payload.seconds, payload.samples))

    @app.post("/api/trajectory")
    def trajectory(payload: TrajectoryRequest, request: Request, response: Response):
        return run(request, response, lambda w, *_: w.trajectory(payload.body_id), cost=25)

    @app.post("/api/launch")
    def launch(payload: LaunchRequest, request: Request, response: Response):
        def apply(w, *_):
            if len(w.sim.particles) >= MAX_BODIES:
                raise SessionError(409, "Body limit reached; reset with fewer cloud bodies")
            return w.add_incoming(**payload.model_dump())
        return run(request, response, apply)

    @app.post("/api/launch-preview")
    def launch_preview(payload: LaunchRequest, request: Request, response: Response):
        # Same validation, ownership, serialization and weighted quota as forecasts.
        return run(request, response,
                   lambda w, *_: w.preview_incoming(**payload.model_dump()), cost=25)

    @app.post("/api/reset")
    def reset(payload: ResetRequest, request: Request, response: Response):
        return run(request, response, lambda w, *_: w.reset(**payload.model_dump()))

    @app.post("/api/replay")
    def replay(payload: ReplayRequest, request: Request, response: Response):
        def apply(w, *_):
            if payload.scenario.cloud_count + 3 > MAX_BODIES:
                raise SessionError(409, "Leave one body slot for the replay arrival")
            w.reset(**payload.scenario.model_dump())
            return w.add_incoming(**payload.launch.model_dump())
        return run(request, response, apply)

    @app.get("/api/checkpoint")
    def checkpoint(request: Request, response: Response):
        return run(request, response, app.state.sessions.export)

    @app.post("/api/restore")
    def restore(payload: dict, request: Request, response: Response):
        return run(request, response, lambda w, sid, key, now:
                   app.state.sessions.restore(w, payload, sid, key, now))

    def minimal(w, action, payload=None):
        from coordinated import CoordinatedCloud
        cloud = CoordinatedCloud(getattr(w, "minimal_snapshot", None))
        if action == "reset":
            cloud = CoordinatedCloud()
        elif action == "launch":
            if cloud.packet is not None:
                raise ValueError("Reset before another launch")
            cloud = CoordinatedCloud()  # identical orbital phase for on/off comparison
            cloud.launch(**payload.model_dump(exclude={"days"}))
        elif action == "step":
            cloud.advance(payload.days)
        result = cloud.state()
        w.minimal_snapshot = cloud.snapshot()
        return result

    # Separate browser identity keeps old workbench recovery from gating First Light.
    minimal_cookie = "dyson_simple_session_v13"

    @app.post("/api/simple/session")
    def minimal_bootstrap(payload: SessionRequest, request: Request, response: Response):
        if payload.has_backup and not request.cookies.get(minimal_cookie):
            raise HTTPException(401, "Resume the saved First Light backup")
        return run(request, response, lambda w, *_: minimal(w, "state"),
                   cookie_name=minimal_cookie, recovery_token=payload.recovery_token)

    @app.post("/api/simple/recover")
    def minimal_recover(payload: RecoveryRequest, request: Request, response: Response):
        return run(request, response, lambda w, *_: minimal(w, "state"),
                   cookie_name=minimal_cookie, recovery_token=payload.credential,
                   recovery_capsule=payload.capsule)

    @app.delete("/api/simple/session")
    def minimal_forget(response: Response):
        # Forget only this view's cookie; do not delete any world or browser backup.
        response.delete_cookie(minimal_cookie, path="/api", httponly=True, samesite="strict")
        response.delete_cookie(minimal_cookie, path="/", httponly=True, samesite="strict")
        return {"status": "forgotten"}

    @app.get("/api/simple")
    def minimal_state(request: Request, response: Response):
        return run(request, response, lambda w, *_: minimal(w, "state"), cookie_name=minimal_cookie)

    @app.post("/api/simple/{action}")
    def minimal_action(action: str, payload: MinimalLaunch, request: Request, response: Response):
        if action not in ("launch", "step", "reset"):
            raise HTTPException(404, "Unknown action")
        return run(request, response, lambda w, *_: minimal(w, action, payload), cookie_name=minimal_cookie)

    @app.get("/simple")
    def minimal_frontend():
        return FileResponse(Path(__file__).with_name("simple.html"), headers={"Cache-Control": "no-store"})

    @app.get("/")
    def browser_frontend():
        return FileResponse(Path(__file__).with_name("rebound.html"))

    @app.get("/explorer.js")
    def explorer_client():
        return FileResponse(Path(__file__).with_name("explorer.js"), media_type="text/javascript",
                            headers={"Cache-Control": "no-cache"})

    @app.get("/motion.js")
    def motion_client():
        return FileResponse(Path(__file__).with_name("motion.js"), media_type="text/javascript",
                            headers={"Cache-Control": "no-cache"})

    @app.get("/laboratory.js")
    def laboratory_client():
        return FileResponse(Path(__file__).with_name("laboratory.js"), media_type="text/javascript",
                            headers={"Cache-Control": "no-cache"})

    @app.get("/recovery.js")
    def recovery_client():
        return FileResponse(Path(__file__).with_name("recovery.js"), media_type="text/javascript",
                            headers={"Cache-Control": "no-cache"})

    @app.get("/sandbox.js")
    def sandbox_client():
        return FileResponse(Path(__file__).with_name("sandbox.js"), media_type="text/javascript",
                            headers={"Cache-Control": "no-cache"})

    @app.get("/sandbox.css")
    def sandbox_style():
        return FileResponse(Path(__file__).with_name("sandbox.css"), media_type="text/css",
                            headers={"Cache-Control": "no-cache"})

    return app


app = create_app()

