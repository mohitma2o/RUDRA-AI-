"""
RUDRA AI - Pydantic Models for Chat
Request/Response schemas for the chat API.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str = Field(..., description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request body for sending a chat message."""
    message: str = Field(..., min_length=1, description="User's message text")
    conversation_id: Optional[int] = Field(None, description="Existing conversation ID, or None for new")
    model: Optional[str] = Field(None, description="Override the default model")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature")
    stream: bool = Field(True, description="Whether to stream the response")


class ChatResponse(BaseModel):
    """Response body for a chat message."""
    conversation_id: int
    message_id: int
    role: str = "assistant"
    content: str
    model: str
    timestamp: str


class ConversationSummary(BaseModel):
    """Summary of a conversation for the sidebar list."""
    id: int
    title: str
    message_count: int
    created_at: str
    updated_at: str


class ConversationDetail(BaseModel):
    """Full conversation with all messages."""
    id: int
    title: str
    messages: list[ChatMessage]
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    """Response for a single message."""
    id: int
    conversation_id: int
    role: str
    content: str
    timestamp: str
