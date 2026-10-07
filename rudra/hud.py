"""Small pywebview demo HUD with non-blocking state updates."""

import threading
from pathlib import Path
from typing import Optional


class RudraHud:
    """Own the pywebview window and update it from the voice pipeline."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._window = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            import webview
        except ImportError:
            print("pywebview is not installed; the demo HUD is disabled.")
            return

        html_path = Path(__file__).parent / "hud" / "hud.html"
        self._window = webview.create_window(
            "Rudra",
            url=html_path.as_uri(),
            size=(460, 680),
            resizable=False,
            on_top=True,
        )
        webview.start()

    def set_state(self, state: str) -> None:
        if self._window is None:
            return
        try:
            self._window.evaluate_js(f"window.setState({state!r})")
        except Exception as exc:
            print(f"HUD state update failed: {exc}")

    def set_transcript(self, user_text: str, response_text: str) -> None:
        if self._window is None:
            return
        try:
            self._window.evaluate_js(
                "window.setTranscript(%s, %s)"
                % (repr(user_text), repr(response_text))
            )
        except Exception as exc:
            print(f"HUD transcript update failed: {exc}")
