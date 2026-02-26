"""
Agent Mesh Backend Server
─────────────────────────
FastAPI + WebSocket spine. TUI connects now, web dashboard later.
All agent orchestration flows through here.
"""

import asyncio
import json
import sys
import threading
import uuid
from datetime import datetime
from typing import Optional
from enum import Enum

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn


# ── Models ────────────────────────────────────────────────────────────────────

class AgentStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    COMPLETE = "complete"
    ERROR = "error"

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"

class JobRequest(BaseModel):
    objective: str
    max_revisions: int = 10

class JobState(BaseModel):
    job_id: str = ""
    status: JobStatus = JobStatus.PENDING
    objective: str = ""
    revision_count: int = 0
    max_revisions: int = 10
    verdict: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    history: list = []
    final_output: str = ""


# ── Event Bus ─────────────────────────────────────────────────────────────────

class EventBus:
    """Central event bus — pushes agent activity to all connected WebSockets."""

    def __init__(self):
        self.connections: list[WebSocket] = []
        self.event_log: list[dict] = []
        self.current_job: Optional[JobState] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.agent_states: dict[str, str] = {
            "architect": "idle",
            "coder": "idle",
            "critic": "idle",
        }

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
        await ws.send_json(self._snapshot())

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def _async_emit(self, event: dict):
        """Broadcast an event to all connected WebSocket clients."""
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def emit_sync(self, event_type: str, agent: str, message: str, data: dict = None):
        """Thread-safe emit — called from the flow_runner callback."""
        event = {
            "type": event_type,
            "agent": agent,
            "message": message,
            "data": data or {},
            "timestamp": datetime.now().isoformat(),
        }
        self.event_log.append(event)

        # Update agent states from status events
        if event_type == "agent_status" and agent in self.agent_states:
            status = (data or {}).get("status", "idle")
            self.agent_states[agent] = status

        # Update job state from verdict events
        if event_type == "verdict" and self.current_job:
            self.current_job.verdict = (data or {}).get("verdict", "")

        if event_type == "job_complete" and self.current_job:
            self.current_job.status = JobStatus.COMPLETE
            self.current_job.completed_at = datetime.now().isoformat()
            self.current_job.revision_count = (data or {}).get("revision_count", 0)
            self.current_job.verdict = (data or {}).get("verdict", "")

        # Push to async loop
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._async_emit(event), self._loop)

    def set_loop(self, loop):
        self._loop = loop

    def _snapshot(self) -> dict:
        return {
            "type": "snapshot",
            "agent": "system",
            "message": "Current state",
            "data": {
                "agent_states": dict(self.agent_states),
                "job": self.current_job.model_dump() if self.current_job else None,
                "recent_events": self.event_log[-50:],
            },
            "timestamp": datetime.now().isoformat(),
        }


# ── Mesh Runner ───────────────────────────────────────────────────────────────

class MeshRunner:
    """Runs the agent mesh in a background thread, using flow_runner's event callback."""

    def __init__(self, bus: EventBus):
        self.bus = bus
        self.running = False

    def run_job(self, objective: str, max_revisions: int = 10) -> str:
        self.running = True
        job_id = str(uuid.uuid4())[:8]

        self.bus.current_job = JobState(
            job_id=job_id,
            status=JobStatus.RUNNING,
            objective=objective,
            max_revisions=max_revisions,
            started_at=datetime.now().isoformat(),
        )

        try:
            from flow_runner import AgentMeshFlow, set_event_callback

            # Wire up the event callback — flow emits directly to our bus
            set_event_callback(self.bus.emit_sync)

            self.bus.emit_sync("job_start", "system", f"🚀 Job {job_id}: {objective}")

            flow = AgentMeshFlow()
            flow.state.objective = objective
            flow.state.max_revisions = max_revisions

            result = flow.kickoff()
            final_output = str(result)

            self.bus.current_job.final_output = final_output
            self.bus.current_job.history = flow.state.history

            return final_output

        except Exception as e:
            self.bus.current_job.status = JobStatus.FAILED
            self.bus.current_job.completed_at = datetime.now().isoformat()
            self.bus.emit_sync("error", "system", f"💥 Job failed: {str(e)}")
            raise
        finally:
            self.running = False


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(title="Agent Mesh Server", version="0.5.0")
bus = EventBus()
runner = MeshRunner(bus)


@app.on_event("startup")
async def startup():
    bus.set_loop(asyncio.get_event_loop())


@app.get("/status")
async def get_status():
    return JSONResponse({
        "server": "agent-mesh",
        "version": "0.5.0",
        "agents": dict(bus.agent_states),
        "job": bus.current_job.model_dump() if bus.current_job else None,
        "event_count": len(bus.event_log),
    })


@app.post("/run")
async def run_job(request: JobRequest):
    if runner.running:
        return JSONResponse(
            {"error": "A job is already running"},
            status_code=409
        )

    def _run():
        runner.run_job(request.objective, request.max_revisions)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return JSONResponse({
        "status": "accepted",
        "objective": request.objective,
        "message": "Job started — connect to /ws for live updates"
    })


@app.get("/history")
async def get_history():
    return JSONResponse({
        "events": bus.event_log[-100:],
        "total": len(bus.event_log),
    })


@app.post("/reset")
async def reset():
    bus.event_log.clear()
    bus.current_job = None
    for agent in bus.agent_states:
        bus.agent_states[agent] = "idle"
    return JSONResponse({"status": "reset"})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await bus.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
    except WebSocketDisconnect:
        bus.disconnect(ws)


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🌑 Agent Mesh Server starting on http://localhost:8000")
    print("   WebSocket:  ws://localhost:8000/ws")
    print("   Status:     http://localhost:8000/status")
    print("   Submit job: POST http://localhost:8000/run")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
