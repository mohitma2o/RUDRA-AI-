"""RUDRA AI tray app entry point.

This module starts the background listener thread, loads configuration,
and initializes the tray interface.
"""

import json
import signal
import sys
import threading
from pathlib import Path
from typing import Any, Optional

import pystray
from PIL import Image, ImageDraw

from llm import query_llm
from memory.scriptures import query as query_scripture
from stt import transcribe_audio
from tts import speak_text
from wakeword import start_wakeword_listener, stop_wakeword_listener

CONFIG_PATH = Path(__file__).parent / "config.json"
MODEL_PATH = Path(__file__).parent / "models" / "rudra.onnx"
ICON_PATH = Path(__file__).parent / "tray_icon.ico"


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

        self._notify("Rudra wake word detected. Listening now.")

        try:
            user_text = transcribe_audio()
        except Exception as exc:
            self._notify(f"Speech transcription failed: {exc}")
            return

        if not user_text:
            self._notify("No speech detected. Please try again.")
            return

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
            self._notify(f"Scripture retrieval failed: {exc}")

        try:
            response = query_llm(user_text, context=scripture_context)
        except Exception as exc:
            self._notify(f"LLM query failed: {exc}")
            return

        try:
            speak_text(response)
        except Exception as exc:
            self._notify(f"Speech output failed: {exc}")
        else:
            self._notify("Rudra has responded.")

    def start(self) -> None:
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
