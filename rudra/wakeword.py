"""Wake word listener using openWakeWord, with SpeechRecognition fallback."""

import time
from pathlib import Path
from threading import Event, Thread
from typing import Callable

import numpy as np

_stop_event = Event()


def _ensure_openwakeword_resources() -> bool:
    """Download the shared ONNX resource bundle used by openWakeWord if missing."""
    try:
        import openwakeword
        from openwakeword.utils import download_models
    except Exception:
        return False

    resources_dir = Path(openwakeword.__file__).resolve().parent / "resources"
    models_dir = resources_dir / "models"
    if models_dir.exists() and any(models_dir.glob("*.onnx")):
        return True

    try:
        print("openWakeWord model resources missing; downloading bundled wakeword models...")
        download_models()
        if models_dir.exists() and any(models_dir.glob("*.onnx")):
            return True
    except Exception as exc:
        print(f"openWakeWord resource download failed: {exc}")

    return False


def load_wakeword_model(model_path: str):
    """Load and return the openWakeWord model from disk."""
    from openwakeword.model import Model

    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"Wake word model not found at {path}")

    try:
        return Model(wakeword_models=[str(path)])
    except Exception as exc:
        message = str(exc)
        if "NO_SUCHFILE" in message or "melspectrogram.onnx" in message:
            if _ensure_openwakeword_resources():
                return Model(wakeword_models=[str(path)])
        raise


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


def start_wakeword_listener(callback: Callable[[str], None], model_path: str = "models/rudra.onnx") -> None:
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


def _openwakeword_loop(callback: Callable[[str], None], model) -> None:
    import pyaudio

    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=1280,
    )
    last_trigger = 0.0
    consecutive_hits = 0
    threshold = 0.6

    try:
        while not _stop_event.is_set():
            frame = stream.read(1280, exception_on_overflow=False)
            audio = np.frombuffer(frame, dtype=np.int16)
            predictions = model.predict(audio)

            if not predictions:
                consecutive_hits = 0
                continue

            triggered = False
            for model_name, score in predictions.items():
                current_score = float(score)
                if current_score > threshold:
                    consecutive_hits += 1
                else:
                    consecutive_hits = 0

                if consecutive_hits >= 3 and time.monotonic() >= last_trigger + 1.5:
                    callback(model_name)
                    last_trigger = time.monotonic()
                    consecutive_hits = 0
                    triggered = True
                    break

            if not triggered and not any(float(score) > threshold for score in predictions.values()):
                consecutive_hits = 0

            time.sleep(0.01)
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
