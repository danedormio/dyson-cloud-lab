"""Minimal REBOUND service. Keep production static site unchanged until approval."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from physics import CloudWorld

app = FastAPI(title="Dyson Cloud Laboratory — REBOUND foundation")
world = CloudWorld()

class StepRequest(BaseModel):
    seconds: float = Field(default=3600, gt=0, le=2_592_000)

class LaunchRequest(BaseModel):
    speed_kms: float = Field(default=25, gt=0, le=100_000)
    impact_au: float = Field(default=0.5, ge=-25, le=25)
    offset_degrees: float = Field(default=0, ge=-180, le=180)

class ResetRequest(BaseModel):
    cloud_count: int = Field(default=72, ge=0, le=2000)

@app.get("/health")
def health():
    return {"status":"ok", "engine":"REBOUND IAS15"}

@app.get("/api/state")
def state():
    return world.state()

@app.post("/api/step")
def step(payload: StepRequest):
    try:
        return world.step(payload.seconds)
    except (ValueError, OverflowError) as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/launch")
def launch(payload: LaunchRequest):
    return world.add_incoming(payload.speed_kms, payload.impact_au, payload.offset_degrees)

@app.post("/api/reset")
def reset(payload: ResetRequest):
    return world.reset(payload.cloud_count)

@app.get("/")
def browser_frontend():
    return FileResponse(Path(__file__).with_name("rebound.html"))
