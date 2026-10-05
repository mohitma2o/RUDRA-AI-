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
    "(Hindi, English, or Punjabi). "
    "Never say phrases like 'as an AI', 'I'm an AI assistant', 'I don't have "
    "personal experiences or opinions', or any other disclaimer that breaks "
    "character. Never mention being built by any company or being a language "
    "model. Speak plainly and with conviction, the way a wise, grounded person "
    "would — not with corporate hedging. If you're uncertain about something, "
    "express that the way a thoughtful person would ('I'm not certain, but...'), "
    "not with a formal AI disclaimer."
)

TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "open_application", "description": "Open or launch a desktop or Start Menu application by name. If the user says 'open camera', 'launch the camera', or 'pull up the Camera app', call this with name='Camera'. Opening Camera is not taking a photo.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Application name"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "capture_photo", "description": "Take a photo using the physical webcam only when the user explicitly asks to take or snap a picture/photo. Never use this for 'open camera' or to launch the Camera app.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "capture_and_search", "description": "Take a photo with the physical webcam and search for the image online only when the user explicitly asks to take a photo and search for it. Never use this to launch the Camera application.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "compose_email", "description": "Open a new email draft addressed to the specified recipient.", "parameters": {"type": "object", "properties": {"to": {"type": "string", "description": "Recipient email address"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["to"]}}},
    {"type": "function", "function": {"name": "open_folder", "description": "Open a folder on this computer, including common folders such as Desktop, Documents, and Downloads.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Folder name or path"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "read_screen", "description": "Read visible text from the current screen and summarize it.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "read_document", "description": "Find and read a local document by name, then summarize its contents.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Document name or path"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "search_file", "description": "Search common local folders for a file by name.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "File name or search phrase"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "google_search", "description": "Search the web for the requested topic or query.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "get_system_stats", "description": "Get this computer's CPU, memory, disk, and battery status.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "close_application", "description": "Close a running desktop application by name.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Application name"}}, "required": ["name"]}}},
]

TOOL_ROUTING_INSTRUCTIONS = (
    "\n\nTool routing rules: Interpret the requested action, not just the word camera. "
    "'Open camera', 'open the camera app', 'launch camera', and 'pull up the Camera app' "
    "mean call open_application with name='Camera'. Only requests to take, snap, or capture "
    "a picture/photo mean call capture_photo. Do not take a picture when the user asks to "
    "open the Camera application."
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


def _build_system_context(context: Optional[List[str]] = None, language: Optional[str] = None) -> str:
    system_content = SYSTEM_PROMPT

    lang = (language or "").strip().lower()
    if lang.startswith("hi"):
        system_content += "\n\nAlways answer in Hindi."
    elif lang.startswith("pa"):
        system_content += "\n\nAlways answer in Punjabi."
    else:
        system_content += "\n\nAlways answer in English unless the user clearly speaks Hindi or Punjabi."

    if context:
        scripture_context = "\n\n".join(c.strip() for c in context if c and c.strip())
        if scripture_context:
            system_content += "\n\nScripture context:\n" + scripture_context
    return system_content


def query_ollama_with_tools(prompt: str, context: Optional[List[str]] = None, language: Optional[str] = None):
    """Ask Ollama to answer or select one of Rudra's declared tools."""
    import ollama

    model = _CONFIG.get("ollama_model", "qwen2.5:3b-instruct-q4_K_M")
    thread_count = int(_CONFIG.get("ollama_threads", 4))
    os.environ.setdefault("OLLAMA_NUM_THREAD", str(thread_count))
    return ollama.chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": _build_system_context(context, language) + TOOL_ROUTING_INSTRUCTIONS,
            },
            {"role": "user", "content": prompt},
        ],
        tools=TOOL_SCHEMAS,
    )


def complete_ollama_tool_call(
    prompt: str,
    assistant_message: Any,
    tool_messages: list[dict[str, str]],
    context: Optional[List[str]] = None,
    language: Optional[str] = None,
) -> str:
    """Send executed tool results back to Ollama for a natural spoken reply."""
    import ollama

    model = _CONFIG.get("ollama_model", "qwen2.5:3b-instruct-q4_K_M")
    messages = [
        {"role": "system", "content": _build_system_context(context, language)},
        {"role": "user", "content": prompt},
        assistant_message,
        *tool_messages,
    ]
    response = ollama.chat(model=model, messages=messages)
    message = response.get("message") if isinstance(response, dict) else getattr(response, "message", None)
    content = message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")
    return str(content or "").strip()


def _query_ollama(prompt: str, context: Optional[List[str]] = None, language: Optional[str] = None) -> str:
    model = _CONFIG.get("ollama_model", "qwen2.5:3b-instruct-q4_K_M")
    thread_count = int(_CONFIG.get("ollama_threads", 4))
    os.environ.setdefault("OLLAMA_NUM_THREAD", str(thread_count))

    system_context = _build_system_context(context, language)
    messages = [
        {"role": "system", "content": system_context},
        {"role": "user", "content": prompt},
    ]

    try:
        import ollama

        if hasattr(ollama, "chat"):
            response = ollama.chat(model=model, messages=messages)
            if isinstance(response, dict):
                message = response.get("message") or {}
                if isinstance(message, dict):
                    content = message.get("content", "")
                    if content:
                        return str(content).strip()
                content = response.get("content", "")
                if content:
                    return str(content).strip()
            if hasattr(response, "message"):
                message = getattr(response, "message")
                if hasattr(message, "content"):
                    content = getattr(message, "content")
                    if content:
                        return str(content).strip()
                if isinstance(message, dict):
                    content = message.get("content", "")
                    if content:
                        return str(content).strip()
            return str(response).strip()
    except Exception:
        pass

    prompt_text = system_context + "\n\nUser: " + prompt + "\n\nAssistant:"
    try:
        completed = subprocess.run(
            ["ollama", "run", model, prompt_text],
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


def _query_openai(prompt: str, context: Optional[List[str]] = None, language: Optional[str] = None) -> str:
    try:
        import openai
    except ImportError as exc:
        raise RuntimeError("openai package is required for OPENAI provider.") from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set for OpenAI provider.")
    openai.api_key = api_key

    system_context = _build_system_context(context, language)
    response = openai.ChatCompletion.create(
        model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        messages=[
            {"role": "system", "content": system_context},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()


def _query_anthropic(prompt: str, context: Optional[List[str]] = None, language: Optional[str] = None) -> str:
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
    prompt_text = _build_system_context(context, language)
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


def query_llm(prompt: str, context: Optional[List[str]] = None, language: Optional[str] = None) -> str:
    """Query the configured LLM with an optional scripture context and spoken language hint."""
    backend = get_llm_backend()
    if backend == "ollama":
        return _query_ollama(prompt, context, language)
    if backend == "openai":
        return _query_openai(prompt, context, language)
    if backend == "anthropic":
        return _query_anthropic(prompt, context, language)
    raise RuntimeError(f"Unsupported LLM provider: {backend}")
