"""RUDRA AI FastAPI backend.

Starts the WebSocket /ws/voice pipeline and a /health endpoint.
Spawned by the Electron main process; run directly with:
    python -m uvicorn app.main:app --port 8000
"""

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
import re
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

import httpx
import uvicorn
from fastapi import Body, Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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
from app.documents import router as documents_router, shutdown_document_jobs
from app.ollama import OLLAMA_BASE_URL
from app.tools import hardware as _hardware_tools  # noqa: F401
from app.tools import browser as _browser_tools    # noqa: F401
from app.tools import applications as _application_tools  # noqa: F401
from app.tools import files as _file_tools  # noqa: F401
from .paths import data_dir, load_config, resource_dir, save_user_config
from app.tools.registry import REGISTRY, execute, Tier

@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    await _startup()
    try:
        yield
    finally:
        await _shutdown()


app = FastAPI(title="RUDRA AI Backend", lifespan=_lifespan)
_API_TOKEN = os.environ.get("RUDRA_TOKEN")
if not _API_TOKEN:
    _API_TOKEN = secrets.token_urlsafe(32)
    print(f"[Security] Standalone backend token: {_API_TOKEN}")

_DEV_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)
_PACKAGED_ORIGINS = ("file://", "null")
_IS_DEV = os.environ.get("RUDRA_DEV") == "1"
_ALLOWED_ORIGINS = (*_DEV_ORIGINS, *_PACKAGED_ORIGINS) if _IS_DEV else _PACKAGED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---------------------------------------------------------------------------
# Startup: warm up models
# ---------------------------------------------------------------------------

async def _startup() -> None:
    # Load & warm STT in background thread
    threading.Thread(target=stt_module.warm_up, daemon=True).start()

    # Warm up Ollama (keep model resident in RAM)
    async def _warm_ollama():
        try:
            import httpx
            config = _load_config()
            model = config.get(
                "ollama_voice_model",
                config.get("ollama_model", "qwen2.5:1.5b"),
            )
            payload = {
                "model": model,
                "stream": False,
                "keep_alive": "30m",
                "messages": [{"role": "user", "content": "hi"}],
                "options": {"num_predict": 1, "num_ctx": 512},
            }
            async with httpx.AsyncClient(timeout=15) as c:
                await c.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
            print("[LLM] Ollama warm-up complete.")
        except Exception as e:
            print(f"[LLM] Warm-up failed (non-fatal): {e}")

    asyncio.create_task(_warm_ollama())


async def _shutdown() -> None:
    await shutdown_document_jobs()
    await asyncio.to_thread(_browser_tools.close_browser_runtime)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": time.time(),
        "instance": hashlib.sha256(_API_TOKEN.encode()).hexdigest()[:16],
    }


def _required_model() -> str:
    config = _load_config()
    return config.get("ollama_voice_model", config.get("ollama_model", "qwen2.5:1.5b"))


def _require_api_token(authorization: Optional[str] = Header(default=None)) -> None:
    expected = f"Bearer {_API_TOKEN}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="A valid local API token is required.")


app.include_router(
    documents_router,
    dependencies=[Depends(_require_api_token)],
)


def _document_model() -> str:
    config = _load_config()
    return config.get(
        "ollama_doc_model",
        config.get("ollama_voice_model", config.get("ollama_model", "qwen2.5:3b-instruct-q4_K_M")),
    )


async def ollama_health() -> dict:
    """Report Ollama reachability and exact configured model-tag availability."""
    voice_model = _required_model()
    doc_model = _document_model()
    result = {
        "reachable": False,
        "voice_model": voice_model,
        "voice_model_installed": False,
        "doc_model": doc_model,
        "doc_model_installed": False,
        "models_installed": [],
        "error": None,
    }
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            raise ValueError("Ollama returned an invalid model list.")
        installed_models = [
            str(model.get("name", ""))
            for model in payload["models"]
            if isinstance(model, dict) and model.get("name")
        ]
        installed = {name.casefold() for name in installed_models}
        result["reachable"] = True
        result["models_installed"] = installed_models
        result["voice_model_installed"] = voice_model.casefold() in installed
        result["doc_model_installed"] = doc_model.casefold() in installed
    except httpx.RequestError:
        result["error"] = "Ollama is not running or is not reachable."
    except httpx.HTTPStatusError as exc:
        result["error"] = f"Ollama returned HTTP {exc.response.status_code}."
    except (ValueError, AttributeError) as exc:
        result["error"] = str(exc)
    return result


@app.get("/api/setup/status")
async def setup_status(_: None = Depends(_require_api_token)):
    health = await ollama_health()

    try:
        async with httpx.AsyncClient(timeout=2) as client:
            tts_response = await client.get("https://speech.platform.bing.com")
            tts_online = tts_response.status_code < 500
    except httpx.RequestError:
        tts_online = False

    bundled_stt = resource_dir() / "backend" / "models" / "whisper-base"
    return {
        "ollama_running": health["reachable"],
        "models_installed": health["models_installed"],
        "required_model": health["voice_model"],
        "voice_model": health["voice_model"],
        "voice_model_installed": health["voice_model_installed"],
        "doc_model": health["doc_model"],
        "doc_model_installed": health["doc_model_installed"],
        "stt_ready": bool(getattr(stt_module, "_model", None)) or bundled_stt.is_dir(),
        "tts_online": tts_online,
        "error": health["error"],
    }


class SetupModelRequest(BaseModel):
    model: Optional[str] = None


@app.post("/api/setup/pull-model")
async def pull_setup_model(
    request: SetupModelRequest = Body(default=SetupModelRequest()),
    _: None = Depends(_require_api_token),
):
    allowed_models = {_required_model(), _document_model()}
    required_model = request.model or _required_model()
    if required_model not in allowed_models:
        raise HTTPException(status_code=422, detail="Only the configured voice and document models can be downloaded.")

    async def progress_stream():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_BASE_URL}/api/pull",
                    json={"name": required_model, "stream": True},
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            yield f"data: {line}\n\n"
        except httpx.HTTPStatusError as exc:
            error = json.dumps({"error": f"Ollama returned HTTP {exc.response.status_code}."})
            yield f"data: {error}\n\n"
        except httpx.RequestError as exc:
            error = json.dumps({"error": f"Could not download the model: {exc}"})
            yield f"data: {error}\n\n"

    return StreamingResponse(
        progress_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


# ---------------------------------------------------------------------------
# Config helper
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    return load_config()


# ---------------------------------------------------------------------------
# Fast-path intent matching
# ---------------------------------------------------------------------------

def _empty_args(_: re.Match) -> dict:
    return {}


def _named_arg(match: re.Match) -> dict:
    name = match.group(1).strip(" .!?")
    name = re.sub(r"^(?:my|the|a|an)\s+", "", name, flags=re.IGNORECASE)
    return {"name": name}


FAST_PATH_RULES: list[tuple[re.Pattern, str, Callable[[re.Match], dict]]] = [
    (
        re.compile(
            r"(?:what time is it|what(?:'s| is) the time|current time|"
            r"tell me the time|what date|what is today's date)[.!?]?"
        ),
        "get_time",
        _empty_args,
    ),
    (
        re.compile(
            r"(?:system status|battery status|cpu usage|ram usage|"
            r"system stats|battery level)[.!?]?"
        ),
        "system_status",
        _empty_args,
    ),
    (
        re.compile(r"(?:take (?:a )?screenshot|capture (?:my )?screen|screenshot)[.!?]?"),
        "screenshot",
        _empty_args,
    ),
    (
        re.compile(r"(?:lock screen|lock my screen|lock the screen|lock my pc|lock computer)[.!?]?"),
        "lock_screen",
        _empty_args,
    ),
    (
        re.compile(r"(?:mute|unmute|toggle mute|mute audio|unmute audio)[.!?]?"),
        "volume_mute",
        _empty_args,
    ),
    (
        re.compile(r"(?:pause music|pause video|play pause|pause media)[.!?]?"),
        "media_control",
        lambda _: {"action": "play_pause"},
    ),
    (
        re.compile(r"(?:next track|next song|skip song)[.!?]?"),
        "media_control",
        lambda _: {"action": "next"},
    ),
    (
        re.compile(r"(?:previous track|previous song)[.!?]?"),
        "media_control",
        lambda _: {"action": "prev"},
    ),
    (
        re.compile(r"(?:set )?volume (?:to )?(\d+)[.!?]?"),
        "volume_set",
        lambda m: {"level": int(m.group(1))},
    ),
    (
        re.compile(r"(?:set )?brightness (?:to )?(\d+)[.!?]?"),
        "brightness_set",
        lambda m: {"level": int(m.group(1))},
    ),
    (
        re.compile(r"(?:brightness up|increase brightness)[.!?]?"),
        "brightness_up",
        _empty_args,
    ),
    (
        re.compile(r"(?:brightness down|decrease brightness|dim screen)[.!?]?"),
        "brightness_down",
        _empty_args,
    ),
    (
        re.compile(r"(?:cancel shutdown|cancel restart|abort shutdown)[.!?]?"),
        "cancel_shutdown",
        _empty_args,
    ),
    (
        re.compile(
            r"(?:shutdown computer|shut down computer|turn off the pc|turn off computer)[.!?]?"
        ),
        "shutdown",
        lambda _: {"delay_seconds": 30},
    ),
    (
        re.compile(
            r"(?:restart computer|reboot computer|reboot the pc|restart the pc)[.!?]?"
        ),
        "restart",
        lambda _: {"delay_seconds": 30},
    ),
    (
        re.compile(r"(?:sleep computer|put computer to sleep|sleep pc)[.!?]?"),
        "sleep",
        _empty_args,
    ),
    (
        re.compile(r"open (?:my )?(desktop|documents|downloads|pictures|music|videos)(?: folder)?[.!?]?"),
        "open_folder",
        _named_arg,
    ),
    (
        re.compile(r"open folder (.+?)[.!?]?"),
        "open_folder",
        _named_arg,
    ),
    (
        re.compile(r"open file (.+?)[.!?]?"),
        "open_file",
        _named_arg,
    ),
    (
        re.compile(r"(?:search|find) file (.+?)[.!?]?"),
        "search_file",
        _named_arg,
    ),
    (
        re.compile(r"read (?:document|file) (.+?)[.!?]?"),
        "read_document",
        _named_arg,
    ),
    (
        re.compile(r"summarize (?:document|file) (.+?)[.!?]?"),
        "summarize_document",
        _named_arg,
    ),
    (
        re.compile(r"(?:open|launch|start) (?:application|app) (.+?)[.!?]?"),
        "open_application",
        _named_arg,
    ),
    (
        re.compile(r"(?:close|quit) (?:application|app) (.+?)[.!?]?"),
        "close_application",
        _named_arg,
    ),
    (
        re.compile(r"play\s+(.+?)(?:\s+on youtube)?[.!?]?"),
        "play_youtube",
        lambda m: {"query": m.group(1).strip(" .!?")},
    ),
]


def match_fast_path(raw: str) -> Optional[tuple[str, dict]]:
    """Match common voice commands to instant tools without hitting the LLM."""
    text = raw.lower().strip()
    for pattern, tool, arg_builder in FAST_PATH_RULES:
        match = pattern.fullmatch(text)
        if match:
            return tool, arg_builder(match)
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
        self.llm_status_task: Optional[asyncio.Task] = None

        # Settings (can be updated via 'config' messages)
        cfg = _load_config()
        # Use the fast voice model by default; UI can switch to 3b via settings
        self.model = cfg.get("ollama_voice_model",
                             cfg.get("ollama_model", "qwen2.5:1.5b"))
        self.language = cfg.get("language", "auto")
        self.voice_override: Optional[str] = cfg.get("tts_voice") or None
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

    async def push_llm_status(self) -> None:
        health = await ollama_health()
        await self.send_json({
            "type": "llm_status",
            "reachable": health["reachable"],
            "model": health["voice_model"],
            "installed": health["voice_model_installed"],
            "error": health["error"],
            "doc_model": health["doc_model"],
            "doc_model_installed": health["doc_model_installed"],
        })

    async def report_llm_status(self) -> None:
        while True:
            await asyncio.sleep(10)
            await self.push_llm_status()

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
            if t.cancelled() or self.task is not t:
                return
            error = t.exception()
            if error:
                await self.send_json({"type": "error", "message": str(error)})
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
        persisted = {}
        if "language" in cfg:
            self.language = cfg["language"]
            persisted["language"] = cfg["language"]
        if "voice" in cfg:
            self.voice_override = cfg["voice"] or None
            persisted["tts_voice"] = cfg["voice"]
        if "stt_model" in cfg:
            self.stt_model = cfg["stt_model"]
            stt_module.set_model_size(self.stt_model)
            persisted["stt_model"] = cfg["stt_model"]
        if "llm_model" in cfg:
            self.model = cfg["llm_model"]
            persisted["ollama_voice_model"] = cfg["llm_model"]
        if persisted:
            save_user_config(persisted)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws/voice")
async def ws_voice(ws: WebSocket) -> None:
    origin = ws.headers.get("origin")
    if origin not in _ALLOWED_ORIGINS and not (not _IS_DEV and origin is None):
        print(f"[WS] Rejected origin {origin!r}; closing with code 1008.")
        await ws.close(code=1008)
        return

    await ws.accept()
    try:
        auth_message = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=5))
    except WebSocketDisconnect:
        return
    except (TimeoutError, ValueError):
        await ws.close(code=1008)
        return

    if (
        not isinstance(auth_message, dict)
        or auth_message.get("type") != "auth"
        or not isinstance(auth_message.get("token"), str)
        or not secrets.compare_digest(auth_message["token"], _API_TOKEN)
    ):
        await ws.close(code=1008)
        return

    session = Session(ws)
    await session.send_json({"type": "state", "state": "idle"})
    await session.push_llm_status()
    session.llm_status_task = asyncio.create_task(session.report_llm_status())
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
        if session.llm_status_task:
            session.llm_status_task.cancel()
            await asyncio.gather(session.llm_status_task, return_exceptions=True)
        await session.interrupt()


# ---------------------------------------------------------------------------
# Entry point for direct invocation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("RUDRA_PORT", "8000")), log_level="info")
