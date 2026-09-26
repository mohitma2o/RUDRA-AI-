"""Agent-style orchestration layer for Rudra.

This module converts a natural-language request into a tool call when the user
is asking the assistant to perform an action on the system instead of just
answering a general question.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from rudra.skills.browser import google_search, open_url
    from rudra.skills.files import open_file, search_file
    from rudra.skills.system import APP_COMMAND_MAP, close_application, get_system_stats, open_application
except ImportError:  # pragma: no cover - supports direct script execution
    from skills.browser import google_search, open_url
    from skills.files import open_file, search_file
    from skills.system import APP_COMMAND_MAP, close_application, get_system_stats, open_application

APP_WHITELIST = sorted(APP_COMMAND_MAP.keys(), key=len, reverse=True)


def get_default_search_dirs() -> List[str]:
    """Return sensible default directories to search for user files."""
    home = Path.home()
    candidates = [
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home,
        Path.cwd(),
    ]
    seen = set()
    valid: List[str] = []
    for d in candidates:
        try:
            resolved = str(d.resolve())
            if resolved not in seen and d.exists():
                seen.add(resolved)
                valid.append(resolved)
        except Exception:
            continue
    return valid


def _pick_app_name(prompt: str) -> Optional[str]:
    text = prompt.lower().strip()
    for app in APP_WHITELIST:
        if app in text:
            return app
    return None


def detect_tool_call(prompt: str) -> Optional[Dict[str, Any]]:
    """Detect whether the user's request should trigger a tool call."""
    if not prompt:
        return None

    text = prompt.lower().strip()

    if re.search(r"\b(open|launch|start|run|activate|begin)\b", text):
        app_name = _pick_app_name(text)
        if app_name:
            return {"tool": "open_application", "args": {"name": app_name}}

    if re.search(r"\b(find|search|locate|where is|where's)\b", text):
        match = re.search(r"(?:find|search|locate|where is|where's)\s+(.+?)(?: in | on | from |$)", prompt, flags=re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name:
                return {"tool": "search_file", "args": {"name": name, "directories": get_default_search_dirs()}}

    if re.search(r"\b(google|search the web|browse to|visit|open url)\b", text):
        match = re.search(r"(?:google|search the web|browse to|visit|open url)\s+(.+)", prompt, flags=re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            return {"tool": "google_search", "args": {"query": query}}

    if re.search(r"\b(system stats|cpu|memory|ram|disk|battery)\b", text):
        return {"tool": "get_system_stats", "args": {}}

    if re.search(r"\b(close|quit|kill|stop)\b", text):
        match = re.search(r"(?:close|quit|kill|stop)\s+(.+)", prompt, flags=re.IGNORECASE)
        if match:
            target = match.group(1).strip()
            return {"tool": "close_application", "args": {"name": target}}

    if re.search(r"\b(?:open file|open)\b", text):
        match = re.search(r"(?:open file|open)\s+(.+)", prompt, flags=re.IGNORECASE)
        if match:
            target = match.group(1).strip()
            # Strip conversational filler and determiners from spoken text
            target = re.sub(
                r"\b(?:please|for me|now|right now|on my computer|on my pc)\b",
                "", target, flags=re.IGNORECASE,
            ).strip()
            target = re.sub(
                r"^(?:my|the|a|an)\s+(?:file\s+|document\s+)?",
                "", target, flags=re.IGNORECASE,
            ).strip()
            target = target.strip("'\".,;:?! ")
            if target:
                return {"tool": "open_file", "args": {"name": target}}

    return None


def _clean_spoken_filename(raw: str) -> str:
    """Strip determiners and filler words from a spoken file reference."""
    cleaned = re.sub(
        r"\b(?:please|for me|now|right now|on my computer|on my pc)\b",
        "", raw, flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(
        r"^(?:my|the|a|an)\s+(?:file\s+|document\s+)?",
        "", cleaned, flags=re.IGNORECASE,
    ).strip()
    return cleaned.strip("'\".,;:?! ")


def execute_tool_call(prompt: str) -> str:
    """Run a tool action represented by the user message and return the result."""
    action = detect_tool_call(prompt)
    if not action:
        return ""

    tool = action["tool"]
    args = action.get("args", {})

    try:
        if tool == "open_application":
            result = open_application(args.get("name", ""))
            return f"Done — {result}"
        if tool == "search_file":
            dirs = args.get("directories") or get_default_search_dirs()
            results = search_file(args.get("name", ""), dirs)
            if not results:
                return f"Done — No matching files found for '{args.get('name', '')}'."
            return f"Done — Found {len(results)} match(es): {', '.join(Path(r).name for r in results[:3])}"
        if tool == "google_search":
            result = google_search(args.get("query", ""))
            return f"Done — {result}"
        if tool == "get_system_stats":
            return "Done — System stats ready."
        if tool == "close_application":
            result = close_application(args.get("name", ""))
            return f"Done — {result}"
        if tool == "open_file":
            raw_target = (args.get("name") or "").strip()
            if not raw_target:
                return "Please specify the file to open."

            # Always search first — don't pass raw spoken text to open_file()
            # as a literal path; it will never be a valid path.
            directories = args.get("directories") or get_default_search_dirs()
            clean_name = _clean_spoken_filename(raw_target)
            search_term = clean_name or raw_target

            matches = search_file(search_term, directories)
            # Also try the raw spoken form if cleaning changed it
            if not matches and search_term.lower() != raw_target.lower():
                matches = search_file(raw_target, directories)

            if not matches:
                return f"I couldn't find a file matching '{raw_target}'."

            def rank_key(path_str: str):
                p = Path(path_str)
                name_lower = p.name.lower()
                stem_lower = p.stem.lower()
                query_lower = search_term.lower()
                # Exact filename or stem match scores highest
                is_exact = (
                    name_lower == query_lower
                    or stem_lower == query_lower
                    or name_lower == raw_target.lower()
                    or stem_lower == raw_target.lower()
                )
                try:
                    mtime = p.stat().st_mtime
                except Exception:
                    mtime = 0
                return (1 if is_exact else 0, mtime)

            matches.sort(key=rank_key, reverse=True)
            best_match = matches[0]

            open_result = open_file(best_match)
            if len(matches) > 1:
                candidate_names = ", ".join(Path(m).name for m in matches[:3])
                return (
                    f"Done — Opened {Path(best_match).name} "
                    f"(selected from {len(matches)} matches: {candidate_names})."
                )
            return f"Done — {open_result}"
        if tool == "open_url":
            result = open_url(args.get("url", ""))
            return f"Done — {result}"
    except Exception as exc:
        return f"Done — Tool execution failed: {exc}"

    return "Done — Unsupported tool call."


def agent_response(prompt: str, llm_fn) -> str:
    """Execute an agent-style action when the request is operational, otherwise ask the model."""
    tool_result = execute_tool_call(prompt)
    if tool_result:
        return tool_result

    if llm_fn is None:
        return "I can help with system tasks, file search, browser actions, and general questions."

    return llm_fn(prompt)
