"""Ollama document summarization requests."""

import json

import httpx

from ..ollama import OLLAMA_BASE_URL
from .prompts import build_prompt

OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
MAX_SUMMARY_TOKENS = 350


async def summarize_text(
    text: str,
    model: str,
    *,
    style: str = "brief",
    language: str = "same",
    instructions: str | None = None,
    reduce: bool = False,
) -> str:
    payload = {
        "model": model,
        "stream": False,
        "keep_alive": "5m",
        "messages": [
            {"role": "system", "content": build_prompt(style, language, instructions, reduce=reduce)},
            {"role": "user", "content": json.dumps(text, ensure_ascii=False)},
        ],
        "options": {"num_ctx": 4096, "num_predict": MAX_SUMMARY_TOKENS},
    }
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(OLLAMA_CHAT_URL, json=payload)
            if response.status_code == 404:
                raise RuntimeError(f'model "{model}" not found, run: ollama pull {model}')
            response.raise_for_status()
    except httpx.RequestError as exc:
        raise RuntimeError("Could not reach Ollama for document summarization.") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Ollama returned HTTP {exc.response.status_code} for document summarization.") from exc
    result = response.json().get("message", {}).get("content", "").strip()
    if not result:
        raise RuntimeError("The document model returned an empty note.")
    return result
