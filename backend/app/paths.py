"""Resolve immutable bundled resources and writable Rudra user data."""

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


def save_user_config(updates: dict) -> None:
    """Merge config updates into the writable user configuration file."""
    import json

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
