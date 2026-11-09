"""Thread-safe shared controls for the legacy tray runtime."""

import threading


class AppState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._is_muted = False

    @property
    def is_muted(self) -> bool:
        with self._lock:
            return self._is_muted

    @is_muted.setter
    def is_muted(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("is_muted must be a bool")
        with self._lock:
            self._is_muted = value


state = AppState()
