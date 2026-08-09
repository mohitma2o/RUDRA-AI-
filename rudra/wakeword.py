"""Wake word listener using openWakeWord, with SpeechRecognition fallback."""

from pathlib import Path
from threading import Event, Thread
from typing import Callable

_stop_event = Event()


def load_wakeword_model(model_path: str) -> object:
    """Load and return the openWakeWord model from disk."""
    try:
        import openwakeword as ow
    except ImportError as exc:
        raise RuntimeError(
            "openwakeword is not installed. Install with `pip install openwakeword`."
        ) from exc

    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"Wake word model not found at {path}")

    model_cls = getattr(ow, "Model", None) or getattr(ow, "WakeWordModel", None)
    if model_cls is None:
        raise RuntimeError("openwakeword API not found in imported module.")

    return model_cls(str(path))


def _speech_recognition_loop(callback: Callable[[str], None]) -> None:
    try:
        import speech_recognition as sr
    except ImportError:
        raise RuntimeError(
            "SpeechRecognition is required for fallback wake word detection. "
            "Install with `pip install SpeechRecognition`."
        )

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 1.5
    recognizer.energy_threshold = 300

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
            print("Wake word fallback: microphone initialized.")
            while not _stop_event.is_set():
                try:
                    audio = recognizer.listen(source, timeout=5.0, phrase_time_limit=5.0)
                    text = recognizer.recognize_google(audio).lower()
                    if "rudra" in text or "hey rudra" in text:
                        callback("Rudra")
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    continue
                except sr.RequestError as exc:
                    print("Wake word recognition network error:", exc)
    except OSError as exc:
        raise RuntimeError(
            "Microphone access failed. Check your audio device and try again."
        ) from exc


def start_wakeword_listener(callback: Callable[[str], None], model_path: str = "models/rudra_openwakeword.bin") -> None:
    """Start a wake word listener thread and call callback when Rudra is detected."""
    try:
        model = load_wakeword_model(model_path)
        print("openWakeWord model loaded; starting native wake word loop.")
        thread = Thread(target=_openwakeword_loop, args=(callback, model), daemon=True)
    except Exception as exc:
        print("openWakeWord unavailable; using SpeechRecognition fallback:", exc)
        thread = Thread(target=_speech_recognition_loop, args=(callback,), daemon=True)

    _stop_event.clear()
    thread.start()


def stop_wakeword_listener() -> None:
    """Stop the wake word listener thread."""
    _stop_event.set()


def _openwakeword_loop(callback: Callable[[str], None], model: object) -> None:
    print("openWakeWord loop is not fully configured. Falling back to speech recognition.")
    _speech_recognition_loop(callback)
