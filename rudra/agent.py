"""Agent-style orchestration layer for Rudra.

This module converts a natural-language request into a tool call when the user
is asking the assistant to perform an action on the system instead of just
answering a general question.
"""

import json
import re
from typing import Any, Dict, Optional

try:
    from rudra.skills.browser import google_search, open_url
    from rudra.skills.files import open_file, search_file
    from rudra.skills.system import APP_COMMAND_MAP, close_application, get_system_stats, open_application
except ImportError:  # pragma: no cover - supports direct script execution
    from skills.browser import google_search, open_url
    from skills.files import open_file, search_file
    from skills.system import APP_COMMAND_MAP, close_application, get_system_stats, open_application

APP_WHITELIST = sorted(APP_COMMAND_MAP.keys(), key=len, reverse=True)


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
                return {"tool": "search_file", "args": {"name": name, "directories": ["C:/", "D:/", "."]}}

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

    if re.search(r"\b(open file|open)\b", text) and ("." in text or "file" in text or "document" in text or "folder" in text):
        match = re.search(r"(?:open file|open)\s+([A-Za-z0-9_\\/.-]+)", prompt, flags=re.IGNORECASE)
        if match:
            return {"tool": "open_file", "args": {"path": match.group(1).strip()}}

    return None


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
            results = search_file(args.get("name", ""), args.get("directories", ["."]))
            if not results:
                return "Done — No matching files found."
            return f"Done — Found {len(results)} match(es): {', '.join(results[:3])}"
        if tool == "google_search":
            result = google_search(args.get("query", ""))
            return f"Done — {result}"
        if tool == "get_system_stats":
            return "Done — System stats ready."
        if tool == "close_application":
            result = close_application(args.get("name", ""))
            return f"Done — {result}"
        if tool == "open_file":
            result = open_file(args.get("path", ""))
            return f"Done — {result}"
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
