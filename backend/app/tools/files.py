"""User file tools constrained to the approved personal folders."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from . import registry
from .registry import Tier, resolve_allowed_path, tool

MAX_DOCUMENT_TEXT_CHARS = 3000
MAX_SEARCH_RESULTS = 25
_SKIP_DIRS = {"appdata", "node_modules", ".git", ".gemini", ".vscode", "$recycle.bin"}


def _open_with_default_app(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


@tool(
    name="open_file",
    description="Open a local file from Desktop, Documents, Downloads, Pictures, Music, or Videos.",
    schema={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "File name or approved path"}},
        "required": ["name"],
    },
)
async def open_file(name: str) -> str:
    target, error = resolve_file_reference(name)
    if error:
        return error
    assert target is not None

    try:
        await asyncio.to_thread(_open_with_default_app, target)
    except OSError as exc:
        return f"Failed to open file: {exc}"
    return f"Opened file: {target.name}"


def _folder_shortcut(path: str) -> Optional[Path]:
    normalized = path.strip().lower().strip("\\/")
    if normalized.startswith("my "):
        normalized = normalized[3:]
    return next(
        (root for root in registry.ALLOWED_FILE_ROOTS if root.name.lower() == normalized),
        None,
    )


@tool(
    name="open_folder",
    description="Open a folder inside an approved personal folder.",
    schema={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Folder name or path"}},
        "required": ["path"],
    },
)
async def open_folder(path: str) -> str:
    target = resolve_allowed_path(_folder_shortcut(path) or path)
    if target is None:
        return "Access denied: folder paths must stay inside an approved user folder."
    if not target.exists():
        return f"Folder not found: {target}"
    if not target.is_dir():
        return "The requested path is not a folder."

    try:
        await asyncio.to_thread(_open_with_default_app, target)
    except OSError as exc:
        return f"Failed to open folder: {exc}"
    return f"Opened folder: {target}"


def _find_files(name: str) -> tuple[list[Path], bool, bool]:
    query = name.strip().casefold()
    if not query:
        return [], False, False

    matches: list[Path] = []
    seen: set[Path] = set()
    search_errors: list[OSError] = []
    truncated = False

    def record_error(error: OSError) -> None:
        search_errors.append(error)

    for root in registry.ALLOWED_FILE_ROOTS:
        if not root.is_dir():
            continue
        for current_root, dirs, filenames in os.walk(
            root,
            followlinks=False,
            onerror=record_error,
        ):
            dirs[:] = [
                directory
                for directory in dirs
                if not directory.startswith(".")
                and directory.lower() not in _SKIP_DIRS
                and not directory.startswith("$")
                and resolve_allowed_path(Path(current_root) / directory) is not None
            ]
            for filename in filenames:
                if query not in filename.casefold():
                    continue
                resolved = resolve_allowed_path(Path(current_root) / filename)
                if resolved is None or not resolved.is_file() or resolved in seen:
                    continue
                seen.add(resolved)
                matches.append(resolved)
                if len(matches) > MAX_SEARCH_RESULTS:
                    truncated = True
                    break
            if truncated:
                break
        if truncated:
            break

    return matches[:MAX_SEARCH_RESULTS], truncated, bool(search_errors)


def _search_files(name: str) -> str:
    if not name.strip():
        return "Please specify a file name to search for."
    matches, truncated, had_errors = _find_files(name)
    if not matches:
        message = f"No matching files found for '{name}'."
    else:
        message = "Matching files:\n" + "\n".join(str(path) for path in matches)
    if truncated:
        message += f"\nShowing the first {MAX_SEARCH_RESULTS} results; narrow the search to see more."
    if had_errors:
        message += "\nSome folders could not be searched because access was denied."
    return message


@tool(
    name="search_file",
    description="Search approved personal folders for a file by name.",
    schema={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "File name or search phrase"}},
        "required": ["name"],
    },
)
async def search_file(name: str) -> str:
    return await asyncio.to_thread(_search_files, name)


def resolve_file_reference(name: str) -> tuple[Optional[Path], Optional[str]]:
    candidate = Path(name).expanduser()
    if candidate.is_absolute() or candidate.parent != Path("."):
        target = resolve_allowed_path(candidate)
        if target is None:
            return None, "Access denied: file paths must stay inside an approved user folder."
        if not target.is_file():
            return None, f"File not found: {name}"
        return target, None

    matches, _, had_errors = _find_files(name)
    if not matches:
        message = f"No matching file found for '{name}'."
        if had_errors:
            message += " Some folders could not be searched because access was denied."
        return None, message

    def rank(path: Path) -> tuple[bool, float]:
        try:
            modified_at = path.stat().st_mtime
        except OSError:
            modified_at = 0
        exact_name = (
            path.name.casefold() == candidate.name.casefold()
            or path.stem.casefold() == candidate.stem.casefold()
        )
        return exact_name, modified_at

    matches.sort(key=rank, reverse=True)
    return matches[0], None


def _read_document(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8", errors="replace")
    elif suffix == ".docx":
        from docx import Document

        document = Document(str(path))
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
        parts.extend(
            " | ".join(cell.text for cell in row.cells)
            for table in document.tables
            for row in table.rows
        )
        text = "\n".join(parts)
    elif suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        return f"Unsupported document type: {suffix or '(no extension)'}"

    text = text.strip()
    if not text:
        return "No readable text found in the document."
    if len(text) > MAX_DOCUMENT_TEXT_CHARS:
        marker = "\n[Text truncated.]"
        text = text[: MAX_DOCUMENT_TEXT_CHARS - len(marker)].rstrip() + marker
    return text


@tool(
    name="read_document",
    description="Read text from a local TXT, Markdown, DOCX, or PDF file in an approved folder.",
    schema={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Document name or approved path"}},
        "required": ["name"],
    },
)
async def read_document(name: str) -> str:
    target, error = resolve_file_reference(name)
    if error:
        return error
    assert target is not None

    try:
        return await asyncio.to_thread(_read_document, target)
    except ImportError as exc:
        return f"Document reader dependency is missing: {exc}"
    except (OSError, ValueError) as exc:
        return f"Failed to read document: {exc}"
