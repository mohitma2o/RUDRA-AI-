"""Speech-to-text using faster-whisper, accepting raw PCM bytes from the WebSocket."""

import asyncio
import threading
from typing import Optional

import numpy as np

ALLOWED_LANGS = {"en", "hi", "pa"}
# Whisper often tags Hindi speech as Urdu; remap to Hindi
LANG_REMAP = {"ur": "hi"}

_model = None
_model_lock = threading.Lock()
_model_size = "base"


def set_model_size(size: str) -> None:
    global _model_size, _model
    _model_size = size
    _model = None  # trigger reload on next call


def _load_model() -> object:
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel
            import os
            cpu_threads = int(os.cpu_count() or 4)
            print(f"[STT] Loading faster-whisper '{_model_size}' ({cpu_threads} threads)...")
            _model = WhisperModel(
                _model_size, device="cpu", compute_type="int8", cpu_threads=cpu_threads
            )
            print("[STT] Model loaded.")
    return _model


def warm_up() -> None:
    """Load model and run one silent frame so the first real transcription is fast."""
    model = _load_model()
    silence = np.zeros(16000, dtype=np.float32)  # 1 second of silence
    try:
        list(model.transcribe(silence, beam_size=1, language="en", vad_filter=False)[0])
        print("[STT] Warm-up complete.")
    except Exception as e:
        print(f"[STT] Warm-up failed (non-fatal): {e}")


def transcribe(pcm16_bytes: bytes, language: Optional[str] = None) -> tuple[str, str]:
    """Transcribe raw 16-bit little-endian PCM at 16 kHz.

    Returns (text, lang) where lang is one of 'en', 'hi', 'pa'.
    """
    audio = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    model = _load_model()

    lang_hint = language if language and language != "auto" else None
    segs, info = model.transcribe(
        audio,
        beam_size=1,
        language=lang_hint,
        vad_filter=False,
        condition_on_previous_text=False,
        initial_prompt="Rudra, \u0930\u0941\u0926\u094d\u0930, \u0a30\u0a41\u0a26\u0a30.",  # biases wake word spelling
    )
    text = " ".join(s.text.strip() for s in segs).strip()
    detected = LANG_REMAP.get(info.language, info.language)
    final_lang = detected if detected in ALLOWED_LANGS else "en"
    return text, final_lang


async def transcribe_async(pcm16_bytes: bytes, language: Optional[str] = None) -> tuple[str, str]:
    """Non-blocking wrapper — runs transcription in a thread pool."""
    return await asyncio.to_thread(transcribe, pcm16_bytes, language)
