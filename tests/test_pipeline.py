"""Unit tests for pipeline helpers (WP2/WP9)."""

import sys
import asyncio
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parents[1]))

from backend.app.voice.pipeline import script_lang, SENT_END
from backend.app.voice import pipeline
import httpx


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


def test_tts_voices_cover_english_hindi_and_punjabi():
    assert pipeline.VOICES == {
        "en": "en-US-SteffanNeural",
        "hi": "hi-IN-MadhurNeural",
        "pa": "pa-IN-GurpreetNeural",
    }


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

    def test_fast_path_requires_a_complete_command(self):
        from backend.app.main import match_fast_path

        for text in (
            "display my notes",
            "screenshots are great",
            "replay",
            "what time is it tomorrow",
            "please set volume to 75",
            "I need a system status report",
        ):
            assert match_fast_path(text) is None

    def test_fast_path_accepts_command_punctuation(self):
        from backend.app.main import match_fast_path

        assert match_fast_path("screenshot!") == ("screenshot", {})
        assert match_fast_path("play shiva tandav on youtube.") == (
            "play_youtube",
            {"query": "shiva tandav"},
        )
        assert match_fast_path("open file my report") == (
            "open_file",
            {"name": "report"},
        )
        assert match_fast_path("search file budget") == (
            "search_file",
            {"name": "budget"},
        )
        assert match_fast_path("summarize document my report") == (
            "summarize_document",
            {"name": "report"},
        )
        assert match_fast_path("open folder my documents") == (
            "open_folder",
            {"name": "documents"},
        )
        assert match_fast_path("close app browser") == (
            "close_application",
            {"name": "browser"},
        )


def test_stt_model_size_is_unchanged_without_reload(monkeypatch):
    from backend.app.voice import stt

    loaded_model = object()
    monkeypatch.setattr(stt, "_model", loaded_model)
    stt.set_model_size(stt._model_size)
    assert stt._model is loaded_model


def test_llm_sentences_raises_typed_error_when_ollama_is_unreachable(monkeypatch):
    class FailedStream:
        async def __aenter__(self):
            raise httpx.ConnectError("offline")

        async def __aexit__(self, *_):
            return None

    class FailedClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        def stream(self, *_args, **_kwargs):
            return FailedStream()

    monkeypatch.setattr(pipeline.httpx, "AsyncClient", FailedClient)

    async def run():
        with pytest.raises(pipeline.LLMUnavailableError):
            await pipeline.llm_sentences([], "voice-model", asyncio.Queue())

    asyncio.run(run())


def test_run_turn_reports_and_speaks_offline_when_ollama_is_unreachable(monkeypatch):
    class FailedStream:
        async def __aenter__(self):
            raise httpx.ConnectError("offline")

        async def __aexit__(self, *_):
            return None

    class FailedClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        def stream(self, *_args, **_kwargs):
            return FailedStream()

    monkeypatch.setattr(pipeline.httpx, "AsyncClient", FailedClient)
    monkeypatch.setattr(pipeline, "offline_tts", lambda *_: asyncio.sleep(0, result=b"wav"))
    messages = []
    audio = []

    async def send_json(message):
        messages.append(message)

    async def send_bytes(data):
        audio.append(data)

    asyncio.run(
        pipeline.run_turn(
            send_json=send_json,
            send_bytes=send_bytes,
            history=[],
            user_lang="en",
            model="voice-model",
            turn=1,
        )
    )

    assert any(message.get("code") == "llm_unreachable" for message in messages)
    assert any(message.get("text") == "My language model isn't running." for message in messages)
    assert audio == [b"wav"]


def test_run_main_redirects_missing_stdio_before_starting_uvicorn(monkeypatch):
    from backend import run
    from types import SimpleNamespace

    calls = []
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=lambda *args, **kwargs: calls.append(kwargs)))
    original_stdout, original_stderr = sys.stdout, sys.stderr
    sys.stdout = None
    sys.stderr = None
    redirected_stdout = None
    redirected_stderr = None
    try:
        run.main()
        redirected_stdout, redirected_stderr = sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr
        if redirected_stdout is not None:
            redirected_stdout.close()
        if redirected_stderr is not None:
            redirected_stderr.close()

    assert calls and calls[0]["log_config"] is None
