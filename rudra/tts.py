"""Text-to-speech module using edge-tts."""

import asyncio
import ctypes
import os
import subprocess
import sys
import tempfile
import uuid
import winsound
from pathlib import Path
from typing import Optional

_keep_temp_audio = False
_ACTIVE_MCI_ALIAS: Optional[str] = None

VOICE_MAP = {
    "hi": "hi-IN-MadhurNeural",
    "pa": "pa-IN-AmanNeural",
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
    global _ACTIVE_MCI_ALIAS

    if path.suffix.lower() == ".wav":
        try:
            winsound.PlaySound(str(path), winsound.SND_FILENAME)
            return
        except Exception:
            pass

    alias = f"RudraTTS{uuid.uuid4().hex[:8]}"
    _ACTIVE_MCI_ALIAS = alias
    try:
        ctypes.windll.winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, None)
        ctypes.windll.winmm.mciSendStringW(f'play {alias} wait', None, 0, None)
    finally:
        try:
            ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, None)
        finally:
            _ACTIVE_MCI_ALIAS = None


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
    if not sys.platform.startswith("win"):
        return

    try:
        winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception:
        pass

    alias = _ACTIVE_MCI_ALIAS
    if alias:
        try:
            ctypes.windll.winmm.mciSendStringW(f"stop {alias}", None, 0, None)
        except Exception:
            pass
        try:
            ctypes.windll.winmm.mciSendStringW(f"close {alias}", None, 0, None)
        except Exception:
            pass
        global _ACTIVE_MCI_ALIAS
        _ACTIVE_MCI_ALIAS = None


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
        _run_async(edge_tts.Communicate(text, voice=voice, rate="+15%").save(str(audio_path)))
        print(f"Playing output file: {audio_path}")
        _play_audio_file(audio_path)
    finally:
        if not _keep_temp_audio and audio_path.exists():
            try:
                audio_path.unlink()
            except OSError:
                pass
