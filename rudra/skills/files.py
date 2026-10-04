"""File and folder automation skill helpers."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

MAX_DOCUMENT_TEXT_CHARS = 3000


def open_folder(path: str) -> str:
    """Open a folder path or a common user-folder shortcut."""
    shortcut = path.strip().lower().strip("\\/")
    known_folders = {
        "desktop": Path.home() / "Desktop",
        "documents": Path.home() / "Documents",
        "downloads": Path.home() / "Downloads",
    }
    target = known_folders.get(shortcut, Path(path).expanduser())

    if not target.exists():
        return f"Folder not found: {target}"
    if not target.is_dir():
        return f"Path is not a folder: {target}"

    resolved = str(target.resolve())
    try:
        if os.name == "nt":
            os.startfile(resolved)
        elif sys.platform == "darwin":
            subprocess.run(["open", resolved], check=False)
        else:
            subprocess.run(["xdg-open", resolved], check=False)
        return f"Opened folder: {resolved}"
    except Exception as exc:
        return f"Failed to open folder: {exc}"


def read_document(path: str) -> str:
    """Extract text from a supported document, capped for LLM summarization."""
    target = Path(path)
    if not target.is_file():
        return f"File not found: {path}"

    suffix = target.suffix.lower()
    try:
        if suffix in {".txt", ".md"}:
            text = target.read_text(encoding="utf-8", errors="replace")
        elif suffix == ".docx":
            from docx import Document

            document = Document(str(target))
            parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
            parts.extend(
                " | ".join(cell.text for cell in row.cells)
                for table in document.tables
                for row in table.rows
            )
            text = "\n".join(parts)
        elif suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(target))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            return f"Unsupported document type: {suffix or '(no extension)'}"
    except ImportError:
        if suffix == ".docx":
            return "python-docx is not installed. Install it with `pip install python-docx`."
        if suffix == ".pdf":
            return "pypdf is not installed. Install it with `pip install pypdf`."
        return "Document reader dependency is missing."
    except Exception as exc:
        return f"Failed to read document: {exc}"

    text = text.strip()
    if not text:
        return "No readable text found in the document."
    if len(text) > MAX_DOCUMENT_TEXT_CHARS:
        marker = "\n[Text truncated.]"
        text = text[: MAX_DOCUMENT_TEXT_CHARS - len(marker)].rstrip() + marker
    return text


def search_file(name: str, directories: List[str]) -> List[str]:
    """Search for files matching the name across the provided directories."""
    matches: List[str] = []
    lowered = name.lower().strip()
    if not lowered:
        return []

    skip_dirs = {"appdata", "node_modules", ".git", ".gemini", ".vscode", "$recycle.bin"}
    seen: set = set()

    for base_dir in directories:
        root = Path(base_dir)
        if not root.exists():
            continue

        try:
            for current_root, dirs, files in os.walk(str(root)):
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                    and d.lower() not in skip_dirs
                    and not d.startswith("$")
                ]
                for f in files:
                    if lowered in f.lower():
                        full_path = str((Path(current_root) / f).resolve())
                        if full_path not in seen:
                            seen.add(full_path)
                            matches.append(full_path)
        except (PermissionError, OSError):
            continue

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
