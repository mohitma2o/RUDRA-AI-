"""Speech-to-text transcription module using faster-whisper."""

import tempfile
from pathlib import Path
from typing import Optional

_model = None


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


def transcribe_audio(duration: float = 5.0, silence_timeout: float = 1.5) -> str:
    """Record audio from the microphone and return the transcribed text."""
    try:
        import speech_recognition as sr
    except ImportError as exc:
        raise RuntimeError(
            "SpeechRecognition is required for mic capture. Install with `pip install SpeechRecognition`."
        ) from exc

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = silence_timeout
    recognizer.energy_threshold = 300

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
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
        return ""

    wav_data = audio.get_wav_data()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
        temp.write(wav_data)
        temp_path = Path(temp.name)

    try:
        model = load_stt_model()
        segments, _ = model.transcribe(
            str(temp_path),
            language="auto",
            task="transcribe",
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text)
        return text.strip()
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass
