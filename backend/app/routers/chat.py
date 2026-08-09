"""
RUDRA AI - Chat Router
API endpoints for AI chat conversations.
"""

import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.chat import ChatRequest, ChatResponse, ConversationSummary
from app.services.llm_service import llm_service
from app.database.sqlite_db import (
    create_conversation,
    get_conversations,
    get_conversation_messages,
    add_message,
    update_conversation_title,
    delete_conversation,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("/send")
async def send_message(request: ChatRequest):
    """Send a message and receive a streaming AI response."""

    # Create new conversation if needed
    conversation_id = request.conversation_id
    is_new = conversation_id is None
    if is_new:
        conversation_id = await create_conversation()

    # Save user message
    await add_message(conversation_id, "user", request.message)

    # Build message history for context
    history = await get_conversation_messages(conversation_id)
    messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]

    if request.stream:
        async def event_stream():
            full_response = []
            # Send conversation_id first
            yield f"data: {json.dumps({'type': 'info', 'conversation_id': conversation_id})}\n\n"

            async for chunk in llm_service.generate_stream(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
            ):
                full_response.append(chunk)
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

            # Save complete assistant response
            complete_response = "".join(full_response)
            msg_id = await add_message(conversation_id, "assistant", complete_response)

            # Generate title for new conversations
            if is_new:
                try:
                    title = await llm_service.generate_title(request.message)
                    await update_conversation_title(conversation_id, title)
                    yield f"data: {json.dumps({'type': 'title', 'title': title})}\n\n"
                except Exception as e:
                    logger.error("Title generation error: %s", e)

            yield f"data: {json.dumps({'type': 'done', 'message_id': msg_id})}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Non-streaming response
        response_text = await llm_service.generate(
            messages=messages,
            model=request.model,
            temperature=request.temperature,
        )
        msg_id = await add_message(conversation_id, "assistant", response_text)

        if is_new:
            try:
                title = await llm_service.generate_title(request.message)
                await update_conversation_title(conversation_id, title)
            except Exception:
                pass

        return ChatResponse(
            conversation_id=conversation_id,
            message_id=msg_id,
            content=response_text,
            model=request.model or llm_service.default_model,
            timestamp="",
        )


@router.get("/conversations")
async def list_conversations(limit: int = 50, offset: int = 0):
    """List all conversations."""
    conversations = await get_conversations(limit, offset)
    return {"conversations": conversations}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: int):
    """Get all messages in a conversation."""
    messages = await get_conversation_messages(conversation_id)
    if not messages and conversation_id > 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"conversation_id": conversation_id, "messages": messages}


@router.delete("/conversations/{conversation_id}")
async def remove_conversation(conversation_id: int):
    """Delete a conversation."""
    await delete_conversation(conversation_id)
    return {"status": "deleted", "conversation_id": conversation_id}


@router.get("/status")
async def chat_status():
    """Check AI model status."""
    status = await llm_service.check_ollama_status()
    return status
