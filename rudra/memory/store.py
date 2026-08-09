"""ChromaDB persistence wrapper for Rudra memory data."""

from typing import Any


def save_conversation(conversation_id: int, messages: list[dict[str, Any]]) -> None:
    """Persist a conversation to the memory store."""
    raise NotImplementedError("Memory storage is not implemented yet")


def load_conversation(conversation_id: int) -> list[dict[str, Any]]:
    """Load a conversation from the memory store."""
    raise NotImplementedError("Memory retrieval is not implemented yet")


def list_conversations() -> list[dict[str, Any]]:
    """Return a list of saved conversations."""
    raise NotImplementedError("Conversation listing is not implemented yet")
