"""Text-to-speech module using edge-tts."""

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import winsound
from pathlib import Path
from typing import Optional

_keep_temp_audio = False

VOICE_MAP = {
    "hi": "hi-IN-MadhurNeural",
    "pa": "hi-IN-MadhurNeural",
    "en": "en-IN-PrabhatNeural",
}


def _choose_voice(language: str) -> str:
    lang = (language or "").lower()
    if lang.startswith("hi"):
        return VOICE_MAP["hi"]
    if lang.startswith("pa"):
        return VOICE_MAP["pa"]
    if lang.startswith("en"):
        return VOICE_MAP["en"]
    return VOICE_MAP["en"]


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        if "running event loop" in str(exc):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        raise


def _play_windows_audio(path: Path) -> None:
    import ctypes

    if path.suffix.lower() == ".wav":
        try:
            winsound.PlaySound(str(path), winsound.SND_FILENAME)
            return
        except Exception:
            pass

    alias = f"RudraTTS{uuid.uuid4().hex[:8]}"
    ctypes.windll.winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, None)
    ctypes.windll.winmm.mciSendStringW(f'play {alias} wait', None, 0, None)
    ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, None)


def _play_audio_file(path: Path) -> None:
    if sys.platform.startswith("win"):
        _play_windows_audio(path)
        return

    subprocess.run(["ffplay", "-nodisp", "-autoexit", str(path)], check=False)


def set_temp_audio_mode(enabled: bool) -> None:
    """Enable or disable preserving the generated audio file."""
    global _keep_temp_audio
    _keep_temp_audio = enabled


def stop_speaking() -> None:
    """Stop any active Windows audio playback before listening again."""
    if sys.platform.startswith("win"):
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass


def speak_text(text: str, language: str = "en") -> None:
    """Synthesize and play speech for the given text."""
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError(
            "edge-tts is not installed. Install with `pip install edge-tts`."
        ) from exc

    voice = _choose_voice(language)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp:
        audio_path = Path(temp.name)

    try:
        print(f"Generating speech for voice={voice} and text length={len(text)}")
        _run_async(edge_tts.Communicate(text, voice=voice).save(str(audio_path)))

        if sys.platform.startswith("win"):
            wav_path = audio_path.with_suffix(".wav")
            ffmpeg = shutil.which("ffmpeg")
            if ffmpeg:
                subprocess.run(
                    [ffmpeg, "-y", "-i", str(audio_path), "-acodec", "pcm_s16le", "-ar", "16000", str(wav_path)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if wav_path.exists():
                    audio_path = wav_path

        print(f"Playing output file: {audio_path}")
        _play_audio_file(audio_path)
    finally:
        if not _keep_temp_audio and audio_path.exists():
            try:
                audio_path.unlink()
            except OSError:
                pass
