"""
RUDRA AI - Scripture Knowledge Service
Loads local Vedic scripture text files and exposes a combined guidance context
for the AI assistant.
"""

import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class ScriptureService:
    """Loads local scripture text files for Vedic guidance."""

    def __init__(self):
        self.text_dir = settings.VEDIC_TEXTS_DIR
        self._cached_context: str | None = None

    def _load_texts(self) -> str:
        if self._cached_context is not None:
            return self._cached_context

        if not self.text_dir.exists():
            logger.warning("Vedic texts directory does not exist: %s", self.text_dir)
            self._cached_context = ""
            return self._cached_context

        entries = []
        for file_path in sorted(self.text_dir.glob("*.txt")):
            try:
                content = file_path.read_text(encoding="utf-8").strip()
                if content:
                    entries.append(f"--- {file_path.stem.replace('_', ' ').title()} ---\n{content}")
            except Exception as exc:
                logger.warning("Failed to read scripture file %s: %s", file_path, exc)

        combined = "\n\n".join(entries)
        if len(combined) > 15000:
            combined = combined[:15000] + "\n\n[TRUNCATED: more scriptures are available in the local Vedic texts folder.]"

        self._cached_context = combined
        return combined

    def get_scripture_context(self) -> str:
        """Return scripture text to include in the LLM system context."""
        return self._load_texts()


scripture_service = ScriptureService()
