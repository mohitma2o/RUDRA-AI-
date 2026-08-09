"""LLM routing for Rudra, with Ollama default and optional API provider override."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, List, Optional

from dotenv import load_dotenv

CONFIG_PATH = Path(__file__).parent / "config.json"
DOTENV_PATH = Path(__file__).parent / ".env"
if DOTENV_PATH.exists():
    load_dotenv(dotenv_path=DOTENV_PATH)

SYSTEM_PROMPT = (
    "You are Rudra, a calm, wise, and protective AI companion, named after Lord Shiva. "
    "Speak with warmth and quiet confidence — never robotic, never overly formal. "
    "When the user asks for advice, draw on the wisdom in the provided scripture context "
    "(if relevant) and reference it naturally, the way a wise friend would, not like you're quoting a textbook. "
    "Otherwise answer normally as a sharp, capable assistant. Reply in the same language the user spoke in "
    "(Hindi, English, or Punjabi)."
)


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing LLM config at {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)

_CONFIG = _load_config()


def get_llm_backend() -> str:
    """Return the configured LLM backend name."""
    provider = os.getenv("LLM_PROVIDER") or _CONFIG.get("llm_provider", "ollama")
    return provider.strip().lower()


def _build_system_context(context: Optional[List[str]] = None) -> str:
    system_content = SYSTEM_PROMPT
    if context:
        scripture_context = "\n\n".join(c.strip() for c in context if c and c.strip())
        if scripture_context:
            system_content += "\n\nScripture context:\n" + scripture_context
    return system_content


def _query_ollama(prompt: str, context: Optional[List[str]] = None) -> str:
    model = _CONFIG.get("ollama_model", "qwen2.5:3b-instruct-q4_K_M")
    thread_count = int(_CONFIG.get("ollama_threads", 4))
    os.environ.setdefault("OLLAMA_NUM_THREAD", str(thread_count))

    system_context = _build_system_context(context)
    messages = [
        {"role": "system", "content": system_context},
        {"role": "user", "content": prompt},
    ]

    try:
        import ollama

        client = getattr(ollama, "Ollama", None)
        if client is None:
            raise RuntimeError("Ollama Python client class not found.")
        instance = client()

        if hasattr(instance, "chat_completion"):
            response = instance.chat_completion.create(model=model, messages=messages)
            return getattr(response.choices[0].message, "content", str(response)).strip()

        if hasattr(instance, "chat"):
            response = instance.chat.create(model=model, messages=messages)
            return getattr(response, "content", str(response)).strip()
    except Exception:
        pass

    prompt_text = system_context + "\n\nUser: " + prompt + "\n\nAssistant:"
    try:
        completed = subprocess.run(
            ["ollama", "chat", model, "--no-stream", "--prompt", prompt_text],
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Ollama is not installed or not available in PATH. Install Ollama or set LLM_PROVIDER to openai/anthropic."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Ollama CLI error: {exc.stderr.strip()}") from exc


def _query_openai(prompt: str, context: Optional[List[str]] = None) -> str:
    try:
        import openai
    except ImportError as exc:
        raise RuntimeError("openai package is required for OPENAI provider.") from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set for OpenAI provider.")
    openai.api_key = api_key

    system_context = _build_system_context(context)
    response = openai.ChatCompletion.create(
        model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        messages=[
            {"role": "system", "content": system_context},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()


def _query_anthropic(prompt: str, context: Optional[List[str]] = None) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package is required for Anthropic provider.") from exc

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY must be set for Anthropic provider.")

    client_cls = getattr(anthropic, "Anthropic", None) or getattr(anthropic, "Client", None)
    if client_cls is None:
        raise RuntimeError("Anthropic client class not found in anthropic SDK.")

    client = client_cls(api_key=api_key)
    prompt_text = _build_system_context(context)
    prompt_text += f"\n\nHuman: {prompt}\n\nAssistant:"

    if hasattr(client, "completions"):
        response = client.completions.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-3.5-opu"),
            prompt=prompt_text,
            max_tokens_to_sample=1024,
        )
        return getattr(response, "completion", "").strip()

    if hasattr(client, "create_completion"):
        response = client.create_completion(
            model=os.getenv("ANTHROPIC_MODEL", "claude-3.5-opu"),
            prompt=prompt_text,
            max_tokens_to_sample=1024,
        )
        return getattr(response, "completion", "").strip()

    raise RuntimeError("Unsupported Anthropic SDK API.")


def query_llm(prompt: str, context: Optional[List[str]] = None) -> str:
    """Query the configured LLM with an optional scripture context."""
    backend = get_llm_backend()
    if backend == "ollama":
        return _query_ollama(prompt, context)
    if backend == "openai":
        return _query_openai(prompt, context)
    if backend == "anthropic":
        return _query_anthropic(prompt, context)
    raise RuntimeError(f"Unsupported LLM provider: {backend}")
