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

# Ensure both backend/ and repo root are in sys.path
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.voice import stt as stt_module
from app.voice.pipeline import VOICES, run_turn, script_lang, synth
from app.voice.wake import find_wake, strip_wake
from app.tools import hardware as _hardware_tools  # noqa: F401
from app.tools import browser as _browser_tools    # noqa: F401
from app.tools.registry import REGISTRY, execute, Tier

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
# Fast-path intent matching
# ---------------------------------------------------------------------------

def match_fast_path(raw: str) -> Optional[tuple[str, dict]]:
    """Match common voice commands to instant tools without hitting the LLM."""
    text = raw.lower().strip()
    import re
    # Time / Date
    if any(p in text for p in ("what time", "current time", "what is the time", "tell me the time", "what date", "what is today's date")):
        return ("get_time", {})
    # System status
    if any(p in text for p in ("system status", "battery status", "cpu usage", "ram usage", "system stats", "battery level")):
        return ("system_status", {})
    # Screenshot
    if any(p in text for p in ("take a screenshot", "take screenshot", "capture screen", "screenshot")):
        return ("screenshot", {})
    # Lock screen
    if any(p in text for p in ("lock screen", "lock my screen", "lock the screen", "lock my pc", "lock computer")):
        return ("lock_screen", {})
    # Mute / Unmute
    if text in ("mute", "unmute", "toggle mute", "mute audio", "unmute audio"):
        return ("volume_mute", {})
    # Media controls
    if any(p in text for p in ("pause music", "pause video", "play pause", "pause media")):
        return ("media_control", {"action": "play_pause"})
    if any(p in text for p in ("next track", "next song", "skip song")):
        return ("media_control", {"action": "next"})
    if any(p in text for p in ("previous track", "previous song")):
        return ("media_control", {"action": "prev"})
    # Volume control
    m_vol = re.search(r"(?:set )?volume (?:to )?(\d+)", text)
    if m_vol:
        return ("volume_set", {"level": int(m_vol.group(1))})
    # Brightness control
    m_bri = re.search(r"(?:set )?brightness (?:to )?(\d+)", text)
    if m_bri:
        return ("brightness_set", {"level": int(m_bri.group(1))})
    if "brightness up" in text or "increase brightness" in text:
        return ("brightness_up", {})
    if "brightness down" in text or "decrease brightness" in text or "dim screen" in text:
        return ("brightness_down", {})
    # YouTube play
    m_yt = re.search(r"play (.+?)(?: on youtube|$)", text)
    if m_yt:
        return ("play_youtube", {"query": m_yt.group(1).strip()})
    # Power controls (CONFIRM tier)
    if any(p in text for p in ("shutdown computer", "shut down computer", "turn off the pc", "turn off computer")):
        return ("shutdown", {"delay_seconds": 30})
    if any(p in text for p in ("restart computer", "reboot computer", "reboot the pc", "restart the pc")):
        return ("restart", {"delay_seconds": 30})
    if any(p in text for p in ("sleep computer", "put computer to sleep", "sleep pc")):
        return ("sleep", {})
    if any(p in text for p in ("cancel shutdown", "cancel restart", "abort shutdown")):
        return ("cancel_shutdown", {})
    return None


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
        self.pending_confirm: Optional[asyncio.Future] = None

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

    def handle_confirm(self, approved: bool) -> None:
        if self.pending_confirm and not self.pending_confirm.done():
            self.pending_confirm.set_result(approved)

    async def ask_confirm(self, tool_obj, tool_args: dict) -> bool:
        loop = asyncio.get_running_loop()
        self.pending_confirm = loop.create_future()
        await self.send_json({
            "type": "confirm",
            "tool": tool_obj.name,
            "args": tool_args,
        })
        try:
            return await asyncio.wait_for(self.pending_confirm, timeout=20.0)
        except asyncio.TimeoutError:
            return False
        finally:
            self.pending_confirm = None

    async def speak_direct_reply(self, reply_text: str, user_lang: str) -> None:
        """Speak a direct result without running Ollama."""
        await self.interrupt()
        self.turn_no += 1
        turn = self.turn_no
        self.history.append({"role": "assistant", "content": reply_text})

        lang = script_lang(reply_text, user_lang)
        voice = self.voice_override or VOICES.get(lang, VOICES["en"])

        async with self.send_lock:
            await self.send_json({
                "type": "reply_delta",
                "turn": turn,
                "text": reply_text,
            })

        audio_data, mime = await synth(reply_text, voice, lang)
        if audio_data:
            async with self.send_lock:
                await self.send_json({
                    "type": "audio",
                    "turn": turn,
                    "seq": 0,
                    "lang": lang,
                    "mime": mime,
                })
                await self.send_bytes(audio_data)

        async with self.send_lock:
            await self.send_json({"type": "turn_end", "turn": turn})
            await self.send_json({"type": "state", "state": "idle"})

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

        # Fast-path intent matching before hitting LLM
        fast_match = match_fast_path(command_text)
        if fast_match:
            tool_name, tool_args = fast_match
            result_text = await execute(tool_name, tool_args, confirm=self.ask_confirm)
            await self.speak_direct_reply(result_text, lang)
            return

        await self.start_turn(command_text, lang)

    async def process_text(self, meta: dict) -> None:
        """Process a typed text input (same pipeline, skips STT)."""
        text = meta.get("text", "").strip()
        if not text:
            return
        lang = script_lang(text, "en")
        await self.send_json({"type": "transcript", "text": text, "lang": lang})

        # Fast-path intent matching before hitting LLM
        fast_match = match_fast_path(text)
        if fast_match:
            tool_name, tool_args = fast_match
            result_text = await execute(tool_name, tool_args, confirm=self.ask_confirm)
            await self.speak_direct_reply(result_text, lang)
            return

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
                    session.handle_confirm(msg.get("approved", False))

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
