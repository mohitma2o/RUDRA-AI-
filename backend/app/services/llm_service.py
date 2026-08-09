"""
RUDRA AI - LLM Service
Handles communication with Ollama for AI chat, code generation, and text processing.
Supports streaming responses via Server-Sent Events.
"""

import httpx
import json
import logging
from typing import AsyncGenerator

from app.config import settings
from app.services.scripture_service import scripture_service

logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with Ollama LLM API."""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.default_model = settings.DEFAULT_MODEL
        self.system_prompt = settings.SYSTEM_PROMPT

    async def check_ollama_status(self) -> dict:
        """Check if Ollama is running and list available models."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check Ollama is alive
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    return {
                        "status": "online",
                        "models": models,
                        "default_model": self.default_model,
                        "has_default": self.default_model in models,
                    }
                return {"status": "error", "message": f"Unexpected status: {response.status_code}"}
        except httpx.ConnectError:
            return {
                "status": "offline",
                "message": "Ollama is not running. Please start Ollama first.",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def generate_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat completion from Ollama.
        Yields chunks of the response text as they arrive.
        """
        model = model or self.default_model
        temperature = temperature if temperature is not None else settings.MODEL_TEMPERATURE

        # Prepend system prompt if not already present
        if not messages or messages[0].get("role") != "system":
            messages = [{"role": "system", "content": self.system_prompt}] + messages

        scripture_context = scripture_service.get_scripture_context()
        if scripture_context:
            messages.insert(
                1,
                {
                    "role": "system",
                    "content": (
                        "Reference the following Vedic scripture guidance when you answer, especially for moral advice, life decisions, "
                        "and spiritual counsel:\n\n" + scripture_context
                    ),
                },
            )

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": settings.MODEL_MAX_TOKENS,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield f"Error: Ollama returned status {response.status_code}: {error_text.decode()}"
                        return

                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                chunk = json.loads(line)
                                content = chunk.get("message", {}).get("content", "")
                                if content:
                                    yield content
                                if chunk.get("done", False):
                                    return
                            except json.JSONDecodeError:
                                continue

        except httpx.ConnectError:
            yield "Error: Cannot connect to Ollama. Please make sure Ollama is running (run `ollama serve` in terminal)."
        except httpx.ReadTimeout:
            yield "Error: Response timed out. The model might be loading for the first time. Please try again."
        except Exception as e:
            logger.error("LLM generation error: %s", e, exc_info=True)
            yield f"Error: {str(e)}"

    async def generate(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """
        Generate a complete (non-streaming) chat response.
        Returns the full response text.
        """
        full_response = []
        async for chunk in self.generate_stream(messages, model, temperature):
            full_response.append(chunk)
        return "".join(full_response)

    async def generate_title(self, user_message: str) -> str:
        """Generate a short title for a conversation based on the first message."""
        messages = [
            {
                "role": "system",
                "content": "Generate a very short title (3-6 words) for a conversation that starts with the following message. Return ONLY the title, nothing else.",
            },
            {"role": "user", "content": user_message},
        ]
        title = await self.generate(messages, temperature=0.3)
        # Clean up the title
        title = title.strip().strip('"').strip("'")
        if len(title) > 60:
            title = title[:57] + "..."
        return title or "New Chat"


# Global service instance
llm_service = LLMService()
