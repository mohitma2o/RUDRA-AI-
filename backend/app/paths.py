"""Resolve immutable bundled resources and writable Rudra user data."""

import json
import os
import sys
from pathlib import Path


def resource_dir() -> Path:
    """Return the directory containing packaged resources or the repository."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    """Return the writable per-user data directory, creating it if needed."""
    configured_dir = os.environ.get("RUDRA_DATA_DIR")
    if configured_dir:
        target = Path(configured_dir).expanduser()
    elif os.name == "nt" and os.environ.get("APPDATA"):
        target = Path(os.environ["APPDATA"]) / "Rudra AI"
    else:
        target = resource_dir() / ".rudra"
    target.mkdir(parents=True, exist_ok=True)
    return target


def load_config() -> dict:
    """Load defaults and per-user settings, including the legacy model alias."""
    default_path = resource_dir() / "rudra" / "config.json"
    user_path = data_dir() / "config.json"
    config: dict = {}
    user_config: dict = {}

    for config_path in (default_path, user_path):
        if not config_path.is_file():
            continue
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not load configuration from {config_path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise RuntimeError(f"Configuration at {config_path} must contain a JSON object.")
        config.update(loaded)
        if config_path == user_path:
            user_config = loaded

    if "ollama_voice_model" not in user_config and "ollama_model" in user_config:
        config["ollama_voice_model"] = user_config["ollama_model"]
    return config


def save_user_config(updates: dict) -> None:
    """Merge config updates into the writable user configuration file."""
    config_path = data_dir() / "config.json"
    current: dict = {}
    if config_path.is_file():
        try:
            current = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not read user configuration at {config_path}: {exc}") from exc
        if not isinstance(current, dict):
            raise RuntimeError(f"User configuration at {config_path} must contain a JSON object.")

    current.update(updates)
    temp_path = config_path.with_suffix(".json.tmp")
    try:
        temp_path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(config_path)
    except OSError as exc:
        raise RuntimeError(f"Could not save user configuration at {config_path}: {exc}") from exc
