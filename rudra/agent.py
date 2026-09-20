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
    from rudra.skills.system import close_application, get_system_stats, open_application
except ImportError:  # pragma: no cover - supports direct script execution
    from skills.browser import google_search, open_url
    from skills.files import open_file, search_file
    from skills.system import close_application, get_system_stats, open_application


def detect_tool_call(prompt: str) -> Optional[Dict[str, Any]]:
    """Detect whether the user's request should trigger a tool call."""
    if not prompt:
        return None

    text = prompt.lower().strip()

    if any(keyword in text for keyword in ["open ", "launch ", "start "]):
        for app in ["notepad", "chrome", "edge", "calculator", "file explorer", "explorer", "cmd", "terminal"]:
            if app in text:
                return {
                    "tool": "open_application",
                    "args": {"name": app},
                }

    if any(keyword in text for keyword in ["search for", "find ", "locate "]):
        match = re.search(r"(?:search for|find|locate)\s+(.+?)(?: in | on | from |$)", prompt, flags=re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name:
                return {
                    "tool": "search_file",
                    "args": {"name": name, "directories": ["C:/", "D:/", "."]},
                }

    if any(keyword in text for keyword in ["google ", "search the web", "open url", "browse to"]):
        match = re.search(r"(?:google|search the web|browse to|open url)\s+(.+)", prompt, flags=re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            return {
                "tool": "google_search",
                "args": {"query": query},
            }

    if any(keyword in text for keyword in ["system stats", "cpu", "memory", "disk", "battery"]):
        return {"tool": "get_system_stats", "args": {}}

    if any(keyword in text for keyword in ["close ", "kill "]):
        match = re.search(r"(?:close|kill)\s+(.+)", prompt, flags=re.IGNORECASE)
        if match:
            target = match.group(1).strip()
            return {"tool": "close_application", "args": {"name": target}}

    if ("open file" in text or "open " in text) and ("." in text or "file" in text):
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
            return open_application(args.get("name", ""))
        if tool == "search_file":
            results = search_file(args.get("name", ""), args.get("directories", ["."]))
            return json.dumps(results[:10], ensure_ascii=False) if results else "No matching files found."
        if tool == "google_search":
            return google_search(args.get("query", ""))
        if tool == "get_system_stats":
            return json.dumps(get_system_stats(), ensure_ascii=False)
        if tool == "close_application":
            return close_application(args.get("name", ""))
        if tool == "open_file":
            return open_file(args.get("path", ""))
        if tool == "open_url":
            return open_url(args.get("url", ""))
    except Exception as exc:
        return f"Tool execution failed: {exc}"

    return "Unsupported tool call."


def agent_response(prompt: str, llm_fn) -> str:
    """Execute an agent-style action when the request is operational, otherwise ask the model."""
    tool_result = execute_tool_call(prompt)
    if tool_result:
        return tool_result

    if llm_fn is None:
        return "I can help with system tasks, file search, browser actions, and general questions."

    return llm_fn(prompt)
