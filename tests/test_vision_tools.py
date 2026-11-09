import asyncio
import sys
import types

from backend.app.tools import vision
from backend.app.tools.registry import execute


class FakeLLMManager:
    async def summarize_text(self, model, text, language):
        return f"{model}:{language}:{text}"

    async def analyze_image(self, image, language):
        return f"{language}:{image.decode()}"


async def no_confirmation(*_):
    return False


def test_clipboard_summary_uses_clipboard_as_untrusted_text(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "pyperclip",
        types.SimpleNamespace(paste=lambda: "Kaisa hai bhai?"),
    )
    manager = FakeLLMManager()
    result = asyncio.run(
        execute(
            "summarize_clipboard",
            {},
            no_confirmation,
            context={"llm_manager": manager, "model": "qwen2.5:1.5b", "language": "Hinglish"},
        )
    )

    assert result == "qwen2.5:1.5b:Hinglish:Kaisa hai bhai?"


def test_clipboard_summary_reports_empty_clipboard(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "pyperclip",
        types.SimpleNamespace(paste=lambda: ""),
    )
    result = asyncio.run(
        execute(
            "summarize_clipboard",
            {},
            no_confirmation,
            context={"llm_manager": FakeLLMManager(), "model": "qwen2.5:1.5b", "language": "English"},
        )
    )

    assert "clipboard does not contain readable text" in result


def test_screen_analysis_sends_captured_image_to_local_model(monkeypatch):
    monkeypatch.setattr(vision, "_capture_screen", lambda: b"screen-image")
    result = asyncio.run(
        execute(
            "analyze_screen",
            {},
            no_confirmation,
            context={"llm_manager": FakeLLMManager(), "model": "qwen2.5vl:3b", "language": "English"},
        )
    )

    assert result == "English:screen-image"


def test_camera_tool_uses_legacy_capture_helper(monkeypatch):
    from backend.app.tools import hardware

    class FakeVision:
        @staticmethod
        def capture_photo():
            return "Captured photo to Pictures/Rudra/test.jpg"

    monkeypatch.setitem(sys.modules, "rudra.skills.vision", FakeVision)

    assert asyncio.run(hardware.capture_photo()) == "Captured photo to Pictures/Rudra/test.jpg"
