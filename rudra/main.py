"""RUDRA AI tray app entry point.

This module starts the background listener thread, loads configuration,
and initializes the tray interface.
"""

import json
import signal
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Optional

import pystray
from PIL import Image, ImageDraw

from agent import agent_response, detect_tool_call
from llm import query_llm
from memory.scriptures import query as query_scripture
from stt import prepare_stt_calibration, transcribe_audio
from tts import speak_text, stop_speaking
from wakeword import start_wakeword_listener, stop_wakeword_listener

CONFIG_PATH = Path(__file__).parent / "config.json"
MODEL_PATH = Path(__file__).parent / "models" / "rudra.onnx"
ICON_PATH = Path(__file__).parent / "tray_icon.ico"


def detect_language(text: str) -> str:
    """Infer the language of the transcription for the TTS voice selection."""
    if not text:
        return "en"
    if any(ch in text for ch in "ऀ-ॿ\u0900-\u097F"):
        return "hi"
    if any(ch in text for ch in "ਕ-ੴ\u0A00-\u0A7F"):
        return "pa"
    return "en"


def load_config() -> dict[str, Any]:
    """Load JSON configuration for Rudra."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _create_icon() -> Image.Image:
    if ICON_PATH.exists():
        try:
            return Image.open(str(ICON_PATH))
        except Exception:
            pass

    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), fill=(99, 102, 241, 255))
    draw.rectangle((22, 24, 42, 40), fill=(255, 255, 255, 255))
    draw.rectangle((24, 18, 40, 22), fill=(255, 255, 255, 255))
    return image


class RudraTray:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.paused = False
        self._processing = False
        self._processing_lock = threading.Lock()
        self.icon = pystray.Icon(
            "Rudra",
            _create_icon(),
            "Rudra AI",
            self._build_menu(),
        )
        self._listener_thread: threading.Thread | None = None

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Status", self._show_status),
            pystray.MenuItem("Pause listening", self._toggle_pause),
            pystray.MenuItem("Quit", self._quit),
        )

    def _notify(self, message: str) -> None:
        try:
            self.icon.notify(message)
        except Exception:
            print(message)

    def _show_status(self, icon: Any, item: Any) -> None:
        status = "paused" if self.paused else "listening"
        self._notify(f"Rudra is currently {status}.")

    def _toggle_pause(self, icon: Any, item: Any) -> None:
        self.paused = not self.paused
        state = "paused" if self.paused else "resumed"
        self._notify(f"Wake word listener {state}.")

    def _quit(self, icon: Any, item: Any) -> None:
        stop_wakeword_listener()
        self.icon.stop()
        sys.exit(0)

    def _on_wake(self, phrase: str) -> None:
        if self.paused:
            return

        with self._processing_lock:
            if self._processing:
                print(f"Wake event ignored while processing: {phrase}")
                return
            self._processing = True

        try:
            print(f"Wake word callback fired: {phrase}")
            self._notify("Rudra wake word detected. Listening now.")
            stop_speaking()

            try:
                print("Stage 1: transcribing user speech...")
                speech_result = transcribe_audio()
                user_text = speech_result.get("text", "") if isinstance(speech_result, dict) else str(speech_result)
                language = speech_result.get("language") if isinstance(speech_result, dict) else None
                print(f"Stage 1 result: {user_text!r} (language={language})")
            except Exception as exc:
                print(f"Speech transcription failed: {exc}")
                traceback.print_exc()
                self._notify(f"Speech transcription failed: {exc}")
                return

            if not user_text:
                self._notify("No speech detected. Please try again.")
                return

            language = language or detect_language(user_text)
            if detect_tool_call(user_text):
                try:
                    print("Stage 2: dispatching agent tool call...")
                    response = agent_response(user_text, lambda prompt: query_llm(prompt, language=language))
                    print(f"Stage 2 result length: {len(response) if response else 0}")
                except Exception as exc:
                    print(f"Agent execution failed: {exc}")
                    traceback.print_exc()
                    self._notify(f"Agent execution failed: {exc}")
                    return
            else:
                scripture_context: Optional[list[str]] = None
                try:
                    scripture_hits = query_scripture(user_text, k=3)
                    if scripture_hits:
                        scripture_context = [
                            f"{hit.get('source', 'scripture')}: {hit.get('text', '')}"
                            for hit in scripture_hits
                            if hit.get('text')
                        ]
                        if scripture_context:
                            self._notify("Scripture context found for your query.")
                except Exception as exc:
                    print(f"Scripture retrieval failed: {exc}")
                    traceback.print_exc()
                    self._notify(f"Scripture retrieval failed: {exc}")

                try:
                    print("Stage 2: sending prompt to LLM...")
                    response = query_llm(user_text, context=scripture_context, language=language)
                    print(f"Stage 2 result length: {len(response) if response else 0}")
                except Exception as exc:
                    print(f"LLM query failed: {exc}")
                    traceback.print_exc()
                    self._notify(f"LLM query failed: {exc}")
                    return

            try:
                print("Stage 3: speaking response...")
                print(f"Detected response language: {language}")
                speak_text(response, language=language)
            except Exception as exc:
                print(f"Speech output failed: {exc}")
                traceback.print_exc()
                self._notify(f"Speech output failed: {exc}")
            else:
                print("Stage 3 complete: audio playback returned without exception.")
                self._notify("Rudra has responded.")
        finally:
            self._processing = False

    def start(self) -> None:
        prepare_stt_calibration()
        start_wakeword_listener(self._on_wake, str(MODEL_PATH))
        self._notify("Rudra is running in the tray. Say 'Rudra' to wake it.")
        self.icon.run()


def _set_signal_handlers(tray: RudraTray) -> None:
    def handle_exit(signum: int, frame: object | None) -> None:
        stop_wakeword_listener()
        tray.icon.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_exit)


def main() -> None:
    """Start Rudra and initialize background services."""
    config = load_config()
    tray = RudraTray(config)
    _set_signal_handlers(tray)
    tray.start()


if __name__ == "__main__":
    main()
