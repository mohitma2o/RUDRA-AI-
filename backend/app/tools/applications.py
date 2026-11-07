"""Desktop application tools reused from the legacy Windows implementation."""

import asyncio

from .registry import Tier, tool


@tool(
    name="open_application",
    description="Open an installed desktop application by name.",
    schema={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Application name"}},
        "required": ["name"],
    },
)
async def open_application(name: str) -> str:
    from rudra.skills.system import open_application as open_legacy_application

    return await asyncio.to_thread(open_legacy_application, name)


@tool(
    name="close_application",
    description="Close a running desktop application by name; may discard unsaved work.",
    tier=Tier.CONFIRM,
    schema={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Application name"}},
        "required": ["name"],
    },
)
async def close_application(name: str) -> str:
    from rudra.skills.system import close_application as close_legacy_application

    return await asyncio.to_thread(close_legacy_application, name)
