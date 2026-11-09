"""Shared Ollama endpoint configuration."""

import os


_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip().rstrip("/")
if "://" not in _host:
    _host = f"http://{_host}"

OLLAMA_BASE_URL = _host
