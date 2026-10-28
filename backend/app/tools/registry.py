"""Tool registry with AUTO / CONFIRM safety tiers.

Tools are registered via the @tool() decorator. When a tool has tier=CONFIRM,
the session must ask the user for approval before calling run().
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Allowed roots for file operations — never access outside these
ALLOWED_FILE_ROOTS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "Pictures",
    Path.home() / "Music",
    Path.home() / "Videos",
]


class Tier(str, Enum):
    AUTO = "auto"          # Run immediately, no confirmation needed
    CONFIRM = "confirm"    # Must ask user first (spoken + in-app button)


@dataclass
class Tool:
    name: str
    description: str
    tier: Tier
    schema: dict           # JSON Schema for arguments
    run: Callable[..., Awaitable[str]]


REGISTRY: dict[str, Tool] = {}


def tool(
    name: str,
    description: str,
    tier: Tier = Tier.AUTO,
    schema: Optional[dict] = None,
):
    """Decorator to register an async function as a tool."""
    def decorator(fn: Callable[..., Awaitable[str]]) -> Callable:
        REGISTRY[name] = Tool(
            name=name,
            description=description,
            tier=tier,
            schema=schema or {"type": "object", "properties": {}},
            run=fn,
        )
        return fn
    return decorator


def _validate_args(t: Tool, args: dict) -> Optional[str]:
    """Basic argument validation against the tool schema. Returns error msg or None."""
    required = t.schema.get("required", [])
    for r in required:
        if r not in args:
            return f"Missing required argument: {r}"
    return None


async def execute(
    name: str,
    args: dict,
    confirm: Callable[[Tool, dict], Awaitable[bool]],
    activity_log: Optional[list] = None,
) -> str:
    """Look up a tool, optionally get confirmation, then run it.

    confirm: async callable(tool, args) -> bool
    """
    if name not in REGISTRY:
        logger.warning("Unknown tool requested: %s", name)
        return f"Unknown tool: {name}"

    t = REGISTRY[name]

    # Validate args
    err = _validate_args(t, args)
    if err:
        return f"Tool argument error: {err}"

    # Require confirmation for CONFIRM tier tools
    if t.tier is Tier.CONFIRM:
        approved = await confirm(t, args)
        if not approved:
            if activity_log is not None:
                activity_log.append({"tool": name, "args": args, "status": "cancelled"})
            return "Cancelled."

    try:
        result = await t.run(**args)
    except Exception as e:
        logger.error("Tool %s failed: %s", name, e)
        result = f"Tool error: {e}"

    if activity_log is not None:
        activity_log.append({"tool": name, "args": args, "result": result, "status": "done"})

    return result
