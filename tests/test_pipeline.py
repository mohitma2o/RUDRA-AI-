"""Unit tests for pipeline helpers (WP2/WP9)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from backend.app.voice.pipeline import script_lang, SENT_END


class TestScriptLang:
    def test_english(self):
        assert script_lang("Hello, how are you?") == "en"

    def test_hindi_devanagari(self):
        assert script_lang("\u0906\u092a \u0915\u0948\u0938\u0947 \u0939\u0948\u0902") == "hi"

    def test_punjabi_gurmukhi(self):
        assert script_lang("\u0a24\u0a41\u0a38\u0a40\u0a02 \u0a15\u0a3f\u0a35\u0a47\u0a02 \u0a39\u0a4b") == "pa"

    def test_mixed_prefers_majority(self):
        # More Devanagari letters should return 'hi'
        text = "\u0906\u092a \u0915\u0948\u0938\u0947 ok"
        result = script_lang(text)
        assert result == "hi"

    def test_empty_returns_default(self):
        assert script_lang("") == "en"
        assert script_lang("", "hi") == "hi"


class TestSentenceEnd:
    def test_splits_on_period(self):
        text = "Hello world. How are you?"
        parts = SENT_END.split(text)
        assert len(parts) >= 2
        assert parts[0].endswith(".")

    def test_splits_on_question_mark(self):
        text = "What is that? Tell me more."
        parts = SENT_END.split(text)
        assert len(parts) >= 2

    def test_splits_on_danda(self):
        # Devanagari danda \u0964
        text = "\u0906\u092a \u0920\u0940\u0915 \u0939\u0948\u0902\u0964 \u0927\u0928\u094d\u092f\u0935\u093e\u0926\u0964"
        parts = SENT_END.split(text)
        assert len(parts) >= 2

    def test_no_split_midsentence(self):
        text = "Hello world"
        parts = SENT_END.split(text)
        assert len(parts) == 1  # no sentence boundary


class TestToolTiers:
    """Ensure CONFIRM tools never run without approval."""

    def test_confirm_tool_requires_approval(self):
        import asyncio
        from backend.app.tools.registry import REGISTRY, execute, Tier

        # Import hardware tools to populate registry
        import backend.app.tools.hardware  # noqa: F401

        shutdown_tool = REGISTRY.get("shutdown")
        assert shutdown_tool is not None, "shutdown tool must be registered"
        assert shutdown_tool.tier is Tier.CONFIRM, "shutdown must require confirmation"

        lock_tool = REGISTRY.get("lock_screen")
        assert lock_tool is not None, "lock_screen tool must be registered"
        assert lock_tool.tier is Tier.AUTO, "lock_screen should be AUTO"

    def test_confirm_tool_cancelled_without_approval(self):
        import asyncio
        from backend.app.tools.registry import execute
        import backend.app.tools.hardware  # noqa: F401

        async def _run():
            activity = []
            async def _reject(t, args):
                return False

            result = await execute(
                "shutdown",
                {"delay_seconds": 30},
                confirm=_reject,
                activity_log=activity,
            )
            assert result == "Cancelled."
            assert any(a["status"] == "cancelled" for a in activity)

        asyncio.run(_run())


class TestFastPath:
    def test_fast_path_intents(self):
        from backend.app.main import match_fast_path

        assert match_fast_path("what time is it") == ("get_time", {})
        assert match_fast_path("tell me the time") == ("get_time", {})
        assert match_fast_path("mute audio") == ("volume_mute", {})
        assert match_fast_path("set volume to 75") == ("volume_set", {"level": 75})
        assert match_fast_path("volume 40") == ("volume_set", {"level": 40})
        assert match_fast_path("set brightness to 80") == ("brightness_set", {"level": 80})
        assert match_fast_path("take a screenshot") == ("screenshot", {})
        assert match_fast_path("lock my pc") == ("lock_screen", {})
        assert match_fast_path("play shiva tandav stotram on youtube") == (
            "play_youtube",
            {"query": "shiva tandav stotram"},
        )
        assert match_fast_path("turn off the pc") == ("shutdown", {"delay_seconds": 30})
        assert match_fast_path("cancel shutdown") == ("cancel_shutdown", {})
        assert match_fast_path("what is quantum computing") is None  # Goes to LLM
