"""
RUDRA AI - System Monitor & Window Control Router
API endpoints for real-time system monitoring, wake word activation, and desktop window controls.
"""

import json
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.services.system_service import system_service
from app.services.wake_word_service import wake_word_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["System & Window Controls"])

# Active event connections (Electron main process & Frontend UI)
event_subscribers: set[WebSocket] = set()


@router.get("/stats")
async def get_system_stats():
    """Get current system statistics."""
    stats = system_service.get_system_stats()
    return stats.model_dump()


@router.get("/processes")
async def get_processes(limit: int = 20):
    """Get top processes by CPU usage."""
    processes = system_service.get_top_processes(limit)
    return {"processes": [p.model_dump() for p in processes]}


@router.websocket("/stream")
async def system_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time system monitoring."""
    await websocket.accept()
    logger.info("System monitor WebSocket connected")
    try:
        while True:
            stats = system_service.get_system_stats()
            await websocket.send_json(stats.model_dump())
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info("System monitor WebSocket disconnected")
    except Exception as e:
        logger.error("System stream error: %s", e)


# ─── Wake Word & Window Control Endpoints ────────────────────────────

@router.websocket("/events")
async def event_stream(websocket: WebSocket):
    """WebSocket stream for app events (wake word triggers, notifications)."""
    await websocket.accept()
    event_subscribers.add(websocket)
    logger.info("Event subscriber connected (Total: %d)", len(event_subscribers))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        event_subscribers.remove(websocket)
        logger.info("Event subscriber disconnected")


def notify_wake_word():
    """Callback function triggered when 'Rudra' is spoken."""
    logger.info("Broadcasting WAKE_WORD_TRIGGERED to Electron window")
    event = json.dumps({"type": "WAKE_WORD_TRIGGERED", "keyword": "Rudra"})

    loop = asyncio.get_event_loop()
    for ws in list(event_subscribers):
        try:
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(ws.send_text(event), loop)
        except Exception as e:
            logger.error("Failed to broadcast wake word event: %s", e)


# Register notify callback with wake word service
wake_word_service.register_callback(notify_wake_word)


class WakeWordToggleRequest(BaseModel):
    enabled: bool


@router.post("/wake-word/toggle")
async def toggle_wake_word(request: WakeWordToggleRequest):
    """Enable or disable voice wake-word listening."""
    if request.enabled:
        wake_word_service.start_listening()
        return {"status": "enabled", "message": "Listening for wake word 'Rudra'"}
    else:
        wake_word_service.stop_listening()
        return {"status": "disabled", "message": "Wake word listener stopped"}


@router.post("/wake-word/trigger")
async def trigger_wake_word_manual():
    """Manually trigger window popup (for testing or shortcuts)."""
    notify_wake_word()
    return {"status": "triggered", "message": "Rudra wake event dispatched"}
