"""Speech-to-text transcription module using faster-whisper."""

import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

_model = None
_CALIBRATED_ENERGY_THRESHOLD: Optional[int] = None


def set_energy_threshold(value: Optional[int]) -> None:
    """Store the calibrated microphone threshold so it is reused instead of recalibrated every turn."""
    global _CALIBRATED_ENERGY_THRESHOLD
    _CALIBRATED_ENERGY_THRESHOLD = value


def prepare_stt_calibration() -> Optional[int]:
    """Calibrate the microphone once, then reuse the threshold for subsequent listening turns."""
    global _CALIBRATED_ENERGY_THRESHOLD
    try:
        import speech_recognition as sr
    except ImportError:
        return None

    if _CALIBRATED_ENERGY_THRESHOLD is not None:
        return _CALIBRATED_ENERGY_THRESHOLD

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 1.5
    recognizer.energy_threshold = 300

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            _CALIBRATED_ENERGY_THRESHOLD = int(recognizer.energy_threshold)
            return _CALIBRATED_ENERGY_THRESHOLD
    except Exception:
        return None


def load_stt_model(model_name: str = "base") -> object:
    """Load the faster-whisper model specified by name."""
    global _model
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Install with `pip install faster-whisper`."
        ) from exc

    if _model is None:
        _model = WhisperModel(model_name, device="cpu", compute_type="int8")
    return _model


def transcribe_audio(duration: float = 5.0, silence_timeout: float = 1.5) -> Dict[str, Any]:
    """Record audio and return both the transcript text and Whisper's detected language."""
    try:
        import speech_recognition as sr
    except ImportError as exc:
        raise RuntimeError(
            "SpeechRecognition is required for mic capture. Install with `pip install SpeechRecognition`."
        ) from exc

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = silence_timeout
    recognizer.energy_threshold = _CALIBRATED_ENERGY_THRESHOLD or 300

    try:
        with sr.Microphone() as source:
            print("Listening for speech...")
            audio = recognizer.listen(
                source,
                timeout=duration,
                phrase_time_limit=duration,
            )
    except OSError as exc:
        raise RuntimeError(
            "Microphone access failed. Verify your audio device is connected."
        ) from exc
    except sr.WaitTimeoutError:
        print("No speech detected before the timeout elapsed.")
        return {"text": "", "language": None}

    wav_data = audio.get_wav_data()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
        temp.write(wav_data)
        temp_path = Path(temp.name)

    try:
        model = load_stt_model()
        print(f"Transcribing captured audio at {temp_path}...")
        segments, info = model.transcribe(
            str(temp_path),
            task="transcribe",
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text)
        cleaned = text.strip()
        language = getattr(info, "language", None) or None
        print(f"Transcription result: {cleaned!r} (language={language})")
        return {"text": cleaned, "language": language}
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass
