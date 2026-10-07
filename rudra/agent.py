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
    from rudra.skills.browser import compose_email, google_search, open_url
    from rudra.skills.files import open_file, open_folder, read_document, search_file
    from rudra.skills.screen import read_screen
    from rudra.skills.system import close_application, get_system_stats, open_application
    from rudra.skills.vision import capture_photo, reverse_image_search
except ImportError:  # pragma: no cover - supports direct script execution
    from skills.browser import compose_email, google_search, open_url
    from skills.files import open_file, open_folder, read_document, search_file
    from skills.screen import read_screen
    from skills.system import close_application, get_system_stats, open_application
    from skills.vision import capture_photo, reverse_image_search


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


def detect_tool_call(prompt: str) -> Optional[Dict[str, Any]]:
    """Detect whether the user's request should trigger a tool call."""
    if not prompt:
        return None

    text = prompt.lower().strip()

    if re.search(r"\b(open url|browse to|visit|google|search the web)\b", text):
        match = re.search(r"(?:google|search the web|browse to|visit|open url)\s+(.+)", prompt, flags=re.IGNORECASE)
        if match:
            return {"tool": "google_search", "args": {"query": match.group(1).strip()}}

    if re.search(r"\btake\s+(?:a\s+)?(?:picture|photo)\b", text):
        return {
            "tool": "capture_photo",
            "args": {"reverse_search": bool(re.search(r"\bsearch\s+for\s+it\b", text))},
        }

    email_match = re.search(r"\bsend\s+an\s+email\s+to\s+([^\s,;]+)|\bemail\s+([^\s,;]+)", prompt, flags=re.IGNORECASE)
    if email_match:
        recipient = (email_match.group(1) or email_match.group(2)).strip().strip("<>.,;:!?").strip("\"'")
        if recipient:
            return {"tool": "compose_email", "args": {"to": recipient}}

    if re.search(r"\b(?:what(?:'s| is) on my screen|read my screen|read this page)\b", text):
        return {"tool": "read_screen", "args": {}}

    if re.search(r"\b(?:help me debug this|what's wrong with this code|read this error)\b", text):
        return {"tool": "debug_screen", "args": {}}

    document_match = re.search(r"\bwhat does\s+(.+?)\s+say\b", prompt, flags=re.IGNORECASE)
    if not document_match:
        document_match = re.search(r"\b(?:summarize|read me)\s+(.+)", prompt, flags=re.IGNORECASE)
    if document_match:
        target = _clean_spoken_filename(document_match.group(1))
        if target:
            return {"tool": "read_document", "args": {"name": target}}

    folder_match = re.search(
        r"\bopen\s+(?:my\s+)?(desktop|documents|downloads)(?:\s+folder)?\b",
        prompt,
        flags=re.IGNORECASE,
    )
    if folder_match:
        return {"tool": "open_folder", "args": {"path": folder_match.group(1)}}

    explicit_file = re.search(r"\bopen file\s+(.+)", prompt, flags=re.IGNORECASE)
    if explicit_file:
        target = _clean_spoken_filename(explicit_file.group(1))
        if target and target.lower() != "explorer":
            return {"tool": "open_file", "args": {"name": target}}

    open_match = re.search(r"\b(?:open|launch|start|run|activate|begin)\s+(.+)", prompt, flags=re.IGNORECASE)
    if open_match:
        target = _clean_spoken_filename(open_match.group(1))
        if target:
            return {"tool": "open_application", "args": {"name": target}}

    if re.search(r"\b(find|search|locate|where is|where's)\b", text):
        match = re.search(r"(?:find|search|locate|where is|where's)\s+(.+?)(?: in | on | from |$)", prompt, flags=re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name:
                return {"tool": "search_file", "args": {"name": name, "directories": get_default_search_dirs()}}

    if re.search(r"\b(system stats|cpu|memory|ram|disk|battery)\b", text):
        return {"tool": "get_system_stats", "args": {}}

    if re.search(r"\b(close|quit|kill|stop)\b", text):
        match = re.search(r"(?:close|quit|kill|stop)\s+(.+)", prompt, flags=re.IGNORECASE)
        if match:
            target = match.group(1).strip()
            return {"tool": "close_application", "args": {"name": target}}

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


def _resolve_open_file_target(raw_target: str, directories: Optional[List[str]] = None) -> tuple[Optional[str], List[str], str]:
    """Search candidate dirs first and rank the best real file match for a spoken name."""
    directories = directories or get_default_search_dirs()
    clean_name = _clean_spoken_filename(raw_target)
    search_term = clean_name or raw_target

    matches = search_file(search_term, directories)
    if not matches and search_term.lower() != raw_target.lower():
        matches = search_file(raw_target, directories)

    if not matches:
        return None, [], search_term

    def rank_key(path_str: str):
        p = Path(path_str)
        name_lower = p.name.lower()
        stem_lower = p.stem.lower()
        query_lower = search_term.lower()
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

    ordered_matches = sorted(matches, key=rank_key, reverse=True)
    return search_term, ordered_matches, search_term


def _execute_open_file(raw_target: str, directories: Optional[List[str]] = None) -> str:
    search_term, matches, _ = _resolve_open_file_target(raw_target, directories)
    if not matches:
        return f"I couldn't find a file matching '{search_term or raw_target}'."

    best_match = matches[0]
    open_result = open_file(best_match)
    if len(matches) > 1:
        candidate_names = ", ".join(Path(match).name for match in matches[:3])
        return (
            f"Done — Opened {Path(best_match).name} "
            f"(selected from {len(matches)} matches: {candidate_names})."
        )
    return f"Done — {open_result}"


def _is_skill_error(result: str) -> bool:
    return result.startswith((
        "Failed",
        "Unable",
        "Could not",
        "No readable text",
        "Unsupported",
        "File not found",
        "Folder not found",
        "Path is not a folder",
        "OpenCV",
        "mss ",
        "EasyOCR ",
        "python-docx ",
        "pypdf ",
        "Pillow ",
            "Document reader dependency",
            "Playwright ",
            "Image file not found",
            "No recipient",
    ))


def _summarize_extracted_text(text: str, source: str, llm_fn) -> str:
    if not llm_fn:
        return f"I couldn't summarize the {source} because the language model is unavailable."
    prompt = f"Briefly summarize or read back the key content of this {source} text:\n{text[:3000]}"
    try:
        return f"Done — {llm_fn(prompt)}"
    except Exception as exc:
        return f"Failed to summarize {source}: {exc}"


def _execute_tool_action(tool: str, args: Dict[str, Any], llm_fn=None, prompt: str = "") -> str:
    try:
        if tool == "open_application":
            app_name = args.get("name", "")
            result = open_application(app_name)
            if result.endswith("Application not found.") and re.match(r"\s*open\b", prompt, flags=re.IGNORECASE):
                return _execute_open_file(app_name)
            if (
                result.startswith("Failed to open")
                or result.startswith("Could not open")
                or result.startswith("No application")
            ):
                return result
            return f"Done — {result}"
        if tool in {"capture_photo", "capture_and_search"}:
            capture_result = capture_photo()
            if not capture_result.startswith("Captured photo to "):
                return capture_result
            if tool != "capture_and_search" and not args.get("reverse_search"):
                return f"Done — {capture_result}"
            photo_path = capture_result.removeprefix("Captured photo to ")
            if not Path(photo_path).is_file():
                return f"Failed to locate captured photo: {photo_path}"
            search_result = reverse_image_search(photo_path)
            if _is_skill_error(search_result):
                return f"{capture_result}; {search_result}"
            return f"Done — {capture_result}; {search_result}"
        if tool == "compose_email":
            result = compose_email(
                args.get("to", ""),
                subject=args.get("subject", ""),
                body=args.get("body", ""),
            )
            return result if _is_skill_error(result) else f"Done — {result}"
        if tool == "open_folder":
            result = open_folder(args.get("path", ""))
            return result if _is_skill_error(result) else f"Done — {result}"
        if tool in {"read_screen", "debug_screen"}:
            text = read_screen()
            if _is_skill_error(text):
                return text
            if tool == "debug_screen":
                if not llm_fn:
                    return "I couldn't debug the screen because the language model is unavailable."
                prompt_text = (
                    "The following is code/error text read from the user's screen. "
                    "Identify likely bugs or explain the error, briefly and practically: "
                    f"{text[:3000]}"
                )
                try:
                    return f"Done — {llm_fn(prompt_text)}"
                except Exception as exc:
                    return f"Failed to debug screen: {exc}"
            return _summarize_extracted_text(text, "screen", llm_fn)
        if tool == "read_document":
            target = args.get("name", "")
            _, matches, search_term = _resolve_open_file_target(target)
            supported = {".txt", ".md", ".docx", ".pdf"}
            readable_matches = [path for path in matches if Path(path).suffix.lower() in supported]
            if not readable_matches:
                return f"I couldn't find a readable document matching '{search_term or target}'."
            text = read_document(readable_matches[0])
            if _is_skill_error(text):
                return text
            return _summarize_extracted_text(text, "document", llm_fn)
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
            return _execute_open_file(raw_target, args.get("directories"))
        if tool == "open_url":
            result = open_url(args.get("url", ""))
            return f"Done — {result}"
    except Exception as exc:
        return f"Done — Tool execution failed: {exc}"

    return "Done — Unsupported tool call."


def execute_tool_call(prompt: str, llm_fn=None) -> str:
    """Run a regex-detected action as the compatibility fallback."""
    action = detect_tool_call(prompt)
    if not action:
        return ""
    return _execute_tool_action(action["tool"], action.get("args", {}), llm_fn, prompt)


def _response_field(value: Any, name: str, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _plain_arguments(arguments: Any) -> Dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    if hasattr(arguments, "model_dump"):
        return arguments.model_dump()
    if hasattr(arguments, "dict"):
        return arguments.dict()
    return {}


def agent_response(
    prompt: str,
    llm_fn,
    tool_call_fn=None,
    tool_followup_fn=None,
    context: Optional[List[str]] = None,
    language: Optional[str] = None,
) -> str:
    """Prefer native model tool calls, retaining regex dispatch as a fallback."""
    model_message = None
    model_content = ""
    if tool_call_fn:
        try:
            response = tool_call_fn(prompt)
            model_message = _response_field(response, "message")
            calls = _response_field(model_message, "tool_calls", []) or []
        except Exception as exc:
            print(f"LLM tool calling unavailable; trying regex fallback: {exc}")
        else:
            model_content = str(_response_field(model_message, "content", "") or "").strip()
            if calls:
                tool_messages = []
                for call in calls:
                    function = _response_field(call, "function", {})
                    tool_name = _response_field(function, "name", "")
                    arguments = _plain_arguments(_response_field(function, "arguments", {}))
                    result = _execute_tool_action(tool_name, arguments, llm_fn, prompt)
                    tool_messages.append({"role": "tool", "content": result})
                if tool_followup_fn:
                    try:
                        spoken_reply = tool_followup_fn(model_message, tool_messages)
                    except Exception as exc:
                        print(f"Tool action completed but final narration failed: {exc}")
                    else:
                        if spoken_reply:
                            return spoken_reply
                return "\n".join(message["content"] for message in tool_messages)

    fallback_result = execute_tool_call(prompt, llm_fn=llm_fn)
    if fallback_result:
        return fallback_result
    if model_content:
        return model_content

    if llm_fn is None:
        return "I can help with system tasks, file search, browser actions, and general questions."

    return llm_fn(prompt)
