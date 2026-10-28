"""RUDRA AI FastAPI backend.

Starts the WebSocket /ws/voice pipeline and a /health endpoint.
Spawned by the Electron main process; run directly with:
    python -m uvicorn app.main:app --port 8000
"""

import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# Make sure the repo root is on the path so we can import rudra.* skills
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.voice import stt as stt_module
from app.voice.pipeline import VOICES, run_turn, script_lang
from app.voice.wake import find_wake, strip_wake

app = FastAPI(title="RUDRA AI Backend")

# ---------------------------------------------------------------------------
# Startup: warm up models
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def _startup() -> None:
    # Load & warm STT in background thread
    threading.Thread(target=stt_module.warm_up, daemon=True).start()

    # Warm up Ollama (keep model resident in RAM)
    async def _warm_ollama():
        try:
            import httpx
            config = _load_config()
            model = config.get("ollama_model", "qwen2.5:1.5b")
            payload = {
                "model": model,
                "stream": False,
                "keep_alive": "30m",
                "messages": [{"role": "user", "content": "hi"}],
                "options": {"num_predict": 1, "num_ctx": 512},
            }
            async with httpx.AsyncClient(timeout=15) as c:
                await c.post("http://localhost:11434/api/chat", json=payload)
            print("[LLM] Ollama warm-up complete.")
        except Exception as e:
            print(f"[LLM] Warm-up failed (non-fatal): {e}")

    asyncio.create_task(_warm_ollama())


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}


# ---------------------------------------------------------------------------
# Config helper
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    cfg_path = _REPO_ROOT / "rudra" / "config.json"
    if cfg_path.exists():
        with cfg_path.open(encoding="utf-8") as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# WebSocket session
# ---------------------------------------------------------------------------

class Session:
    """Per-connection state for the voice WebSocket."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.turn_no: int = 0
        self.task: Optional[asyncio.Task] = None
        self.history: list[dict] = []
        self.send_lock = asyncio.Lock()

        # Settings (can be updated via 'config' messages)
        cfg = _load_config()
        # Use the fast voice model by default; UI can switch to 3b via settings
        self.model = cfg.get("ollama_voice_model",
                             cfg.get("ollama_model", "qwen2.5:1.5b"))
        self.language = cfg.get("language", "auto")
        self.voice_override: Optional[str] = None
        self.stt_model = cfg.get("stt_model", "base")
        stt_module.set_model_size(self.stt_model)

        # Wake-word follow-up window: if we spoke within 8 s, next utterance
        # is treated as hands-free (no wake word needed)
        self._last_wake_ts: float = 0.0
        self.FOLLOWUP_WINDOW = 8.0

    # -----------------------------------------------------------------------
    # Sending helpers
    # -----------------------------------------------------------------------

    async def send_json(self, data: dict) -> None:
        try:
            await self.ws.send_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    async def send_bytes(self, data: bytes) -> None:
        try:
            await self.ws.send_bytes(data)
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Turn management
    # -----------------------------------------------------------------------

    async def interrupt(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        await self.send_json({"type": "state", "state": "listening"})

    async def start_turn(self, user_text: str, user_lang: str) -> None:
        await self.interrupt()
        self.turn_no += 1
        turn = self.turn_no
        self.history.append({"role": "user", "content": user_text})
        await self.send_json({"type": "state", "state": "thinking"})

        self.task = asyncio.create_task(
            run_turn(
                send_json=self.send_json,
                send_bytes=self.send_bytes,
                history=self.history,
                user_lang=user_lang,
                model=self.model,
                turn=turn,
                voice_override=self.voice_override,
                send_lock=self.send_lock,
            )
        )

        async def _on_done(t: asyncio.Task) -> None:
            if t.exception():
                await self.send_json({"type": "error", "message": str(t.exception())})
            await self.send_json({"type": "state", "state": "idle"})

        self.task.add_done_callback(lambda t: asyncio.ensure_future(_on_done(t)))

    # -----------------------------------------------------------------------
    # Utterance processing
    # -----------------------------------------------------------------------

    async def process_utterance(self, meta: dict, pcm16: bytes) -> None:
        """Transcribe PCM audio and decide whether to respond."""
        t_stt = time.monotonic()
        lang_hint = None if self.language == "auto" else self.language
        text, lang = await stt_module.transcribe_async(pcm16, lang_hint)
        stt_ms = int((time.monotonic() - t_stt) * 1000)

        if not text.strip():
            await self.send_json({"type": "state", "state": "idle"})
            return

        await self.send_json({"type": "transcript", "text": text, "lang": lang})
        await self.send_json({"type": "state", "state": "thinking"})

        mode = meta.get("mode", "wake")
        command_text = text

        if mode == "wake":
            in_followup = (time.monotonic() - self._last_wake_ts) < self.FOLLOWUP_WINDOW
            wake_token = find_wake(text)
            if wake_token:
                command_text = strip_wake(text, wake_token)
                self._last_wake_ts = time.monotonic()
            elif not in_followup:
                # No wake word and not in follow-up window — ignore
                await self.send_json({"type": "state", "state": "idle"})
                return
        else:
            # PTT or hands-free — always respond
            wake_token = find_wake(text)
            if wake_token:
                command_text = strip_wake(text, wake_token)
            self._last_wake_ts = time.monotonic()

        if not command_text.strip():
            command_text = text

        # TODO (WP5): rule-based fast path (time, volume, etc.) goes here
        # before hitting the LLM

        await self.start_turn(command_text, lang)

    async def process_text(self, meta: dict) -> None:
        """Process a typed text input (same pipeline, skips STT)."""
        text = meta.get("text", "").strip()
        if not text:
            return
        lang = script_lang(text, "en")
        await self.send_json({"type": "transcript", "text": text, "lang": lang})
        await self.start_turn(text, lang)

    async def update_config(self, cfg: dict) -> None:
        if "language" in cfg:
            self.language = cfg["language"]
        if "voice" in cfg:
            self.voice_override = cfg["voice"] or None
        if "stt_model" in cfg:
            self.stt_model = cfg["stt_model"]
            stt_module.set_model_size(self.stt_model)
        if "llm_model" in cfg:
            self.model = cfg["llm_model"]


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws/voice")
async def ws_voice(ws: WebSocket) -> None:
    await ws.accept()
    session = Session(ws)
    await session.send_json({"type": "state", "state": "idle"})
    pending_meta: Optional[dict] = None  # metadata frame waiting for binary

    try:
        while True:
            data = await ws.receive()

            if data["type"] == "websocket.disconnect":
                break

            # Text frame (JSON metadata)
            if "text" in data:
                msg = json.loads(data["text"])
                msg_type = msg.get("type", "")

                if msg_type == "utterance":
                    # Next frame will be binary PCM
                    pending_meta = msg
                    await session.send_json({"type": "state", "state": "listening"})

                elif msg_type == "text":
                    await session.process_text(msg)

                elif msg_type == "interrupt":
                    await session.interrupt()

                elif msg_type == "confirm":
                    # TODO (WP5): route confirm reply to the awaiting tool
                    pass

                elif msg_type == "config":
                    await session.update_config(msg)

            # Binary frame (PCM audio following an 'utterance' metadata frame)
            elif "bytes" in data and pending_meta is not None:
                pcm = data["bytes"]
                meta = pending_meta
                pending_meta = None
                await session.process_utterance(meta, pcm)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Unexpected error: {e}")
    finally:
        await session.interrupt()


# ---------------------------------------------------------------------------
# Entry point for direct invocation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )
