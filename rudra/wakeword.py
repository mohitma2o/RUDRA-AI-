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
    """Wake-word fallback using local faster-whisper (no internet required)."""
    try:
        import pyaudio
    except ImportError:
        raise RuntimeError(
            "PyAudio is required for fallback wake word detection. "
            "Install with `pip install pyaudio`."
        )
    import io
    import wave
    import numpy as np

    # Re-use the calibrated energy threshold from stt.py if available.
    try:
        from stt import _CALIBRATED_ENERGY_THRESHOLD as _cal_thresh  # noqa: PLC0415
    except ImportError:
        _cal_thresh = None

    try:
        from faster_whisper import WhisperModel
        _wake_model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=2)
    except Exception as exc:
        raise RuntimeError(f"faster-whisper unavailable for wake fallback: {exc}") from exc

    RATE = 16000
    CHUNK = 1280
    SILENCE_CHUNKS = 20  # ~1.6 s of silence ends a phrase
    ENERGY_THRESHOLD = _cal_thresh or 300

    pa = pyaudio.PyAudio()
    stream = pa.open(format=pyaudio.paInt16, channels=1, rate=RATE,
                     input=True, frames_per_buffer=CHUNK)

    print(f"Wake word fallback (local Whisper): mic ready (threshold={ENERGY_THRESHOLD}).")
    try:
        while not _stop_event.is_set():
            frames = []
            silent_chunks = 0
            recording = False
            while not _stop_event.is_set():
                raw = stream.read(CHUNK, exception_on_overflow=False)
                audio_chunk = np.frombuffer(raw, dtype=np.int16)
                energy = np.abs(audio_chunk).mean()
                if energy > ENERGY_THRESHOLD:
                    recording = True
                    silent_chunks = 0
                    frames.append(raw)
                elif recording:
                    frames.append(raw)
                    silent_chunks += 1
                    if silent_chunks >= SILENCE_CHUNKS:
                        break

            if not frames or _stop_event.is_set():
                continue

            # Build a WAV buffer and transcribe locally
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(RATE)
                wf.writeframes(b"".join(frames))
            buf.seek(0)

            try:
                pcm = np.frombuffer(buf.read(), dtype=np.int16)[44:].astype(np.float32) / 32768.0
                segs, _ = _wake_model.transcribe(
                    pcm, beam_size=1, language="en", vad_filter=False,
                    condition_on_previous_text=False,
                    initial_prompt="Rudra.",
                )
                text = " ".join(s.text.lower().strip() for s in segs)
                if any(w in text for w in ("rudra", "rudhra", "rudar", "rudraa", "roodra")):
                    callback("Rudra")
            except Exception as exc:
                print(f"Wake word fallback transcription error: {exc}")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


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
