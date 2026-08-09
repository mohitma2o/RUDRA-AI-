"""
RUDRA AI - Configuration Module
Centralizes all application settings and environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables with sensible defaults."""

    # Application
    APP_NAME: str = "RUDRA AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # Server
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Ollama LLM
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:3b")
    MODEL_TEMPERATURE: float = float(os.getenv("MODEL_TEMPERATURE", "0.7"))
    MODEL_MAX_TOKENS: int = int(os.getenv("MODEL_MAX_TOKENS", "2048"))

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / "rudra.db"
    CHROMA_DIR: Path = DATA_DIR / "chroma"
    VEDIC_TEXTS_DIR: Path = DATA_DIR / "vedic_texts"
    PLUGINS_DIR: Path = BASE_DIR / "plugins"
    MODELS_DIR: Path = BASE_DIR.parent / "models"
    UPLOADS_DIR: Path = DATA_DIR / "uploads"
    SCREENSHOTS_DIR: Path = DATA_DIR / "screenshots"

    # Voice
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "small")
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    PIPER_VOICE: str = os.getenv("PIPER_VOICE", "en_US-lessac-medium")

    # Vision
    TESSERACT_CMD: str = os.getenv(
        "TESSERACT_CMD",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

    # System prompt for the AI assistant
    SYSTEM_PROMPT: str = """You are RUDRA AI, an intelligent desktop assistant modeled after Jarvis.
You are helpful, confident, concise, and precise. You can help with:
- Answering questions and having conversations
- Writing, debugging, and explaining code
- Summarizing documents and extracting insights
- Automating desktop tasks and controlling applications
- Capturing photos, opening browser searches, and interacting with the system
- Providing thoughtful guidance grounded in Vedic wisdom when appropriate
- Monitoring system performance and providing proactive guidance

Always respond in a calm, professional tone. When asked to perform an action, explain what you will do and then do it. When answering life questions, draw on the spirit of the Vedas, Bhagavad Gita, Upanishads, Ramayana, Mahabharata, and other Hindu scriptures. When unsure, say so honestly and suggest the next best step."""

    def __init__(self):
        """Ensure required directories exist."""
        for dir_path in [
            self.DATA_DIR,
            self.CHROMA_DIR,
            self.VEDIC_TEXTS_DIR,
            self.PLUGINS_DIR,
            self.UPLOADS_DIR,
            self.SCREENSHOTS_DIR,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
