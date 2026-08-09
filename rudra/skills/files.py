"""File and folder automation skill helpers."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List


def search_file(name: str, directories: List[str]) -> List[str]:
    """Search for files matching the name across the provided directories."""
    matches: List[str] = []
    lowered = name.lower()

    for base_dir in directories:
        root = Path(base_dir)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and lowered in path.name.lower():
                matches.append(str(path.resolve()))

    return matches


def open_file(path: str) -> str:
    """Open a file with the default application."""
    target = Path(path)
    if not target.exists():
        return f"File not found: {path}"

    try:
        if os.name == "nt":
            os.startfile(str(target))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(target)], check=False)
        else:
            subprocess.run(["xdg-open", str(target)], check=False)
        return f"Opened file: {target.name}"
    except Exception as exc:
        return f"Failed to open file: {exc}"


def move_file(src: str, dest: str, confirm: bool = False) -> str:
    """Move or rename a file when confirmation is granted."""
    source = Path(src)
    destination = Path(dest)

    if not source.exists():
        return f"Source not found: {src}"
    if not confirm:
        return "Move operation not confirmed." 

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return f"Moved {source.name} to {destination}"
    except Exception as exc:
        return f"Failed to move file: {exc}"


def delete_file(path: str, confirm: bool = False) -> str:
    """Delete a file when confirmation is granted."""
    target = Path(path)
    if not target.exists():
        return f"Path not found: {path}"
    if not confirm:
        return "Delete operation not confirmed." 

    try:
        if target.is_dir():
            shutil.rmtree(target)
            return f"Deleted directory: {target}"
        target.unlink()
        return f"Deleted file: {target}"
    except Exception as exc:
        return f"Failed to delete path: {exc}"
