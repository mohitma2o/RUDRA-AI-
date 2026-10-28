"""Streaming LLM -> sentence splitter -> TTS pipeline.

Architecture:
  llm_sentences()  -- streams Ollama, emits complete sentences into a queue
  run_turn()       -- drains the queue, synthesises each sentence, sends audio
  offline_tts()    -- pyttsx3 fallback when edge-tts / internet is unavailable
"""

import asyncio
import json
import re
import sys
import time
from typing import Awaitable, Callable, Optional

import httpx

OLLAMA_URL = "http://localhost:11434/api/chat"

# Sentence boundary: after .!?  or Devanagari danda  or newline, followed by whitespace
SENT_END = re.compile(r"(?<=[.!?\u0964\n])\s+")

VOICES = {
    "en": "en-IN-PrabhatNeural",
    "hi": "hi-IN-MadhurNeural",
    "pa": "pa-IN-GaganNeural",
}

SYSTEM = (
    "You are Rudra, a calm, wise, and protective AI companion, named after Lord Shiva. "
    "Speak with warmth and quiet confidence. Keep answers to 1-3 short sentences — "
    "concise enough that the user can hear the whole reply quickly. "
    "Reply in the SAME language the user spoke: Devanagari for Hindi, "
    "Gurmukhi for Punjabi, English otherwise. "
    "No markdown, no emojis, no lists, no bullet points, no URLs read aloud. "
    "Never break character with AI disclaimers."
)


def script_lang(text: str, default: str = "en") -> str:
    """Detect language from script — used to pick the right TTS voice per sentence."""
    if not text:
        return default
    letters = max(1, sum(c.isalpha() for c in text))
    gur = sum("\u0A00" <= c <= "\u0A7F" for c in text)
    dev = sum("\u0900" <= c <= "\u097F" for c in text)
    if gur / letters > 0.3:
        return "pa"
    if dev / letters > 0.3:
        return "hi"
    return default


async def synth_edge(text: str, voice: str) -> bytes:
    """Synthesise text with edge-tts, return MP3 bytes."""
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate="+5%")
    out = bytearray()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            out += chunk["data"]
    return bytes(out)


async def offline_tts(text: str, lang: str = "en") -> bytes:
    """pyttsx3 fallback — returns WAV bytes via a temp file."""
    import asyncio, tempfile, os
    from pathlib import Path

    def _synth() -> bytes:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            # Attempt to pick a voice for the language
            voices = engine.getProperty("voices")
            lang_map = {"hi": "hindi", "pa": "punjabi", "en": "english"}
            target = lang_map.get(lang, "english")
            for v in voices:
                if target in v.name.lower():
                    engine.setProperty("voice", v.id)
                    break
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                tmp = tf.name
            engine.save_to_file(text, tmp)
            engine.runAndWait()
            data = Path(tmp).read_bytes()
            os.unlink(tmp)
            return data
        except Exception as e:
            print(f"[TTS] offline_tts failed: {e}")
            return b""

    return await asyncio.to_thread(_synth)


async def synth(text: str, voice: str, lang: str) -> tuple[bytes, str]:
    """Try edge-tts first; fall back to pyttsx3. Returns (audio_bytes, mime)."""
    try:
        data = await synth_edge(text, voice)
        if data:
            return data, "audio/mpeg"
    except Exception as e:
        print(f"[TTS] edge-tts failed ({e}), falling back to pyttsx3")
    data = await offline_tts(text, lang)
    return data, "audio/wav"


async def llm_sentences(
    history: list[dict],
    model: str,
    sentence_queue: asyncio.Queue,
) -> None:
    """Stream Ollama, split into sentences, push each into the queue. Ends with None."""
    payload = {
        "model": model,
        "stream": True,
        "keep_alive": "30m",
        "messages": [
            {"role": "system", "content": SYSTEM},
            *history[-8:],
        ],
        "options": {
            "num_predict": 140,
            "num_ctx": 2048,
            "temperature": 0.5,
        },
    }
    buf = ""
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", OLLAMA_URL, json=payload) as response:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = chunk.get("message", {}).get("content", "")
                    buf += token
                    # Split on sentence boundary
                    if SENT_END.search(buf):
                        *done, buf = SENT_END.split(buf)
                        for s in done:
                            s = s.strip()
                            if s:
                                await sentence_queue.put(s)
        if buf.strip():
            await sentence_queue.put(buf.strip())
    except asyncio.CancelledError:
        pass  # Interruption is expected; cleanup happens in finally
    except Exception as e:
        print(f"[LLM] Stream error: {e}")
    finally:
        await sentence_queue.put(None)  # Sentinel


async def run_turn(
    send_json: Callable[[dict], Awaitable[None]],
    send_bytes: Callable[[bytes], Awaitable[None]],
    history: list[dict],
    user_lang: str,
    model: str,
    turn: int,
    voice_override: Optional[str] = None,
    send_lock: Optional[asyncio.Lock] = None,
) -> None:
    """One complete assistant turn. Cancel this task to interrupt."""
    _lock = send_lock or asyncio.Lock()
    q: asyncio.Queue = asyncio.Queue()
    t_start = time.monotonic()
    timing = {}

    producer = asyncio.create_task(llm_sentences(history, model, q))
    full_reply = []

    try:
        seq = 0
        first_sentence = True
        while True:
            sentence = await q.get()
            if sentence is None:
                break

            if first_sentence:
                timing["llm_first_token_ms"] = int((time.monotonic() - t_start) * 1000)
                first_sentence = False

            lang = script_lang(sentence, user_lang)
            voice = voice_override or VOICES.get(lang, VOICES["en"])
            full_reply.append(sentence)

            # Stream reply text to the UI
            async with _lock:
                await send_json({
                    "type": "reply_delta",
                    "turn": turn,
                    "text": sentence + " ",
                })

            # Synthesise and send audio
            t_tts = time.monotonic()
            audio_data, mime = await synth(sentence, voice, lang)
            if seq == 0:
                timing["tts_first_audio_ms"] = int((time.monotonic() - t_tts) * 1000)
                timing["total_ms"] = int((time.monotonic() - t_start) * 1000)

            if audio_data:
                async with _lock:
                    await send_json({
                        "type": "audio",
                        "turn": turn,
                        "seq": seq,
                        "lang": lang,
                        "mime": mime,
                    })
                    await send_bytes(audio_data)

            seq += 1

        async with _lock:
            await send_json({"type": "turn_end", "turn": turn})

        # Add assistant reply to history
        if full_reply:
            history.append({"role": "assistant", "content": " ".join(full_reply)})

        # Send timing data
        async with _lock:
            await send_json({"type": "timing", **timing})

    finally:
        producer.cancel()
        await asyncio.gather(producer, return_exceptions=True)
