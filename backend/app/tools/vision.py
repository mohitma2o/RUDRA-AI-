"""Explicitly requested clipboard and screen analysis tools."""

import asyncio

from .registry import get_tool_context, tool

MAX_CLIPBOARD_CHARS = 12000


def _read_clipboard() -> str:
    import pyperclip

    text = pyperclip.paste()
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("The clipboard does not contain readable text.")
    return text[:MAX_CLIPBOARD_CHARS]


def _capture_screen() -> bytes:
    import cv2
    import mss
    import mss.tools
    import numpy as np

    with mss.mss() as capture:
        monitor = capture.monitors[0]
        screenshot = capture.grab(monitor)
        png = mss.tools.to_png(screenshot.rgb, screenshot.size)

    image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("The screen capture could not be decoded.")
    height, width = image.shape[:2]
    if width > 1280:
        image = cv2.resize(
            image,
            (1280, max(1, round(height * 1280 / width))),
            interpolation=cv2.INTER_AREA,
        )
    encoded, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 78])
    if not encoded:
        raise RuntimeError("The screen capture could not be encoded.")
    return buffer.tobytes()


@tool("summarize_clipboard", "Summarize text currently on the clipboard, only when explicitly requested.")
async def summarize_clipboard() -> str:
    try:
        text = await asyncio.to_thread(_read_clipboard)
        context = get_tool_context()
        return await context["llm_manager"].summarize_text(
            context["model"],
            text,
            context["language"],
        )
    except Exception as exc:
        return f"Clipboard summary failed: {exc}"


@tool("analyze_screen", "Analyze the current screen using a local Ollama vision model, only when explicitly requested.")
async def analyze_screen() -> str:
    try:
        image = await asyncio.to_thread(_capture_screen)
        context = get_tool_context()
        return await context["llm_manager"].analyze_image(image, context["language"])
    except Exception as exc:
        return f"Screen analysis failed: {exc}"
