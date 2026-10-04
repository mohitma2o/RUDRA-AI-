"""Screen text extraction using Tesseract OCR."""

MAX_SCREEN_TEXT_CHARS = 3000


def read_screen() -> str:
    """Capture the primary display and return OCR text, capped for summarization."""
    try:
        import mss
    except ImportError:
        return "mss is not installed. Install it with `pip install mss`."

    try:
        import pytesseract
    except ImportError:
        return "pytesseract is not installed. Install it with `pip install pytesseract`."

    try:
        from PIL import Image
    except ImportError:
        return "Pillow is not installed. Install it with `pip install Pillow`."

    try:
        with mss.mss() as capture:
            monitor = capture.monitors[1] if len(capture.monitors) > 1 else capture.monitors[0]
            screenshot = capture.grab(monitor)
            image = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
        text = pytesseract.image_to_string(image).strip()
    except pytesseract.pytesseract.TesseractNotFoundError:
        return (
            "Tesseract OCR is not installed or not on PATH. Install the Windows "
            "Tesseract binary from the UB-Mannheim installer and restart Rudra."
        )
    except Exception as exc:
        return f"Failed to read screen: {exc}"

    if not text:
        return "No readable text found on screen."
    if len(text) > MAX_SCREEN_TEXT_CHARS:
        marker = "\n[Text truncated.]"
        text = text[: MAX_SCREEN_TEXT_CHARS - len(marker)].rstrip() + marker
    return text