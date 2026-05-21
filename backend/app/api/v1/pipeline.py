from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from app.services.pipeline_service import pipeline_service, PipelineStatus

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# ── Request / Response Models ──────────────────────────────────────────

class PipelineStartRequest(BaseModel):
    mode: str = "test"                          # test | prod
    platforms: list[str] = ["xhs"]              # xhs, dy, bili, wb
    login_type: str = "qrcode"                  # qrcode | phone | cookie
    headless: bool = False
    schedule: str | None = None                 # daily | weekly | monthly | None


class PipelineStopResponse(BaseModel):
    success: bool
    message: str = ""


# ── REST Endpoints ─────────────────────────────────────────────────────

@router.post("/start")
async def start_pipeline(req: PipelineStartRequest):
    """Start the pipeline with the given parameters.

    The pipeline runs `run_pipeline.py` as a subprocess.
    Logs are streamed via the WebSocket endpoint.
    """
    # Validate
    if req.mode not in ("test", "prod"):
        raise HTTPException(400, "mode must be 'test' or 'prod'")
    for p in req.platforms:
        if p not in ("xhs", "dy", "bili", "wb"):
            raise HTTPException(400, f"unsupported platform: {p}")
    if req.login_type not in ("qrcode", "phone", "cookie"):
        raise HTTPException(400, "login_type must be qrcode/phone/cookie")
    if req.schedule and req.schedule not in ("daily", "weekly", "monthly"):
        raise HTTPException(400, "schedule must be daily/weekly/monthly")
    if req.schedule and req.mode == "test":
        raise HTTPException(400, "schedule is only supported in prod mode")

    result = await pipeline_service.start(
        mode=req.mode,
        platforms=req.platforms,
        login_type=req.login_type,
        headless=req.headless,
        schedule=req.schedule,
    )
    if not result["success"]:
        raise HTTPException(409, result.get("error", "Failed to start pipeline"))
    return result


@router.post("/stop")
async def stop_pipeline():
    """Stop the currently running pipeline."""
    result = await pipeline_service.stop()
    if not result["success"]:
        raise HTTPException(409, result.get("error", "Cannot stop pipeline"))
    return result


@router.get("/status")
async def get_pipeline_status():
    """Get current pipeline status."""
    return pipeline_service.get_status_detail()


# ── WebSocket Endpoint ─────────────────────────────────────────────────

@router.websocket("/ws/logs")
async def pipeline_logs_ws(websocket: WebSocket):
    """WebSocket endpoint for real-time pipeline log streaming.

    Messages sent to clients are JSON objects with:
    - {"type": "log", "line": "..."}        — a log line
    - {"type": "status", "status": "..."}   — pipeline status change
    """
    await pipeline_service.subscribe(websocket)
    try:
        # Keep connection alive; client can send pings
        while True:
            data = await websocket.receive_text()
            # Client can send {"type": "ping"} for keep-alive
            if data.strip() == "ping":
                await websocket.send_text('{"type": "pong"}')
    except WebSocketDisconnect:
        pass
    finally:
        pipeline_service.unsubscribe(websocket)
