"""Wake word listener using openWakeWord, with SpeechRecognition fallback."""

import time
from pathlib import Path
from threading import Event, Thread
from typing import Callable

import numpy as np

_stop_event = Event()


def _select_wakeword_trigger(predictions: dict[str, float], threshold: float = 0.45):
    """Return the strongest wake-word prediction that crossed the activation threshold."""
    if not predictions:
        return None

    best_name = None
    best_score = -1.0
    for name, score in predictions.items():
        try:
            value = float(score)
        except (TypeError, ValueError):
            continue
        if value >= threshold and value > best_score:
            best_name = str(name)
            best_score = value
    return best_name


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

    # Try to reuse the threshold calibrated by stt.py so the threshold stays
    # stable and doesn't drift upward between calls (the 'listens once' bug).
    try:
        from stt import _CALIBRATED_ENERGY_THRESHOLD as _cal_thresh  # noqa: PLC0415
    except ImportError:
        _cal_thresh = None

    recognizer = sr.Recognizer()
    # dynamic_energy_threshold = True causes the threshold to creep up on every
    # loop iteration until no audio is loud enough to trigger recognition.
    recognizer.dynamic_energy_threshold = False
    recognizer.pause_threshold = 1.5
    recognizer.energy_threshold = _cal_thresh or 300

    try:
        with sr.Microphone() as source:
            if _cal_thresh is None:
                recognizer.adjust_for_ambient_noise(source, duration=1.0)
                recognizer.energy_threshold = max(int(recognizer.energy_threshold), 300)
            print(f"Wake word fallback: mic ready (threshold={recognizer.energy_threshold}).")
            while not _stop_event.is_set():
                try:
                    audio = recognizer.listen(source, timeout=5.0, phrase_time_limit=5.0)
                    # en-IN handles Indian-accented English well; "Rudra" is often
                    # misheard as "rudhra", "rudar", etc. \u2014 check both languages.
                    text = ""
                    for lang in ("en-IN", "hi-IN"):
                        try:
                            text = recognizer.recognize_google(audio, language=lang).lower()
                            break
                        except sr.UnknownValueError:
                            continue
                    if any(w in text for w in ("rudra", "rudhra", "rudar", "rudraa")):
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
    threshold = 0.45

    try:
        while not _stop_event.is_set():
            frame = stream.read(1280, exception_on_overflow=False)
            audio = np.frombuffer(frame, dtype=np.int16)
            predictions = model.predict(audio)
            trigger_name = _select_wakeword_trigger(predictions, threshold=threshold)

            if trigger_name and time.monotonic() >= last_trigger + 1.0:
                callback("Rudra")
                last_trigger = time.monotonic()
                print(f"Wake word trigger fired via {trigger_name}.")

            time.sleep(0.01)
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
