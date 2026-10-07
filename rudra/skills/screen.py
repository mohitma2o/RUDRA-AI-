"""Screen text extraction using EasyOCR."""

_reader = None

MAX_SCREEN_TEXT_CHARS = 3000
MAX_OCR_IMAGE_SIDE = 1280


def read_screen() -> str:
    """Capture the primary display and return OCR text, capped for summarization."""
    try:
        import mss
    except ImportError:
        return "mss is not installed. Install it with `pip install mss`."

    try:
        import easyocr
        import numpy as np
        import cv2
    except ImportError:
        return "EasyOCR or its image dependencies are not installed. Install them with `pip install easyocr opencv-python`."

    try:
        with mss.mss() as capture:
            # mss monitor index 0 represents the full virtual desktop on Windows.
            # Capturing it avoids missing content on secondary displays.
            screenshot = capture.grab(capture.monitors[0])
            image = np.frombuffer(screenshot.rgb, dtype=np.uint8).reshape(
                screenshot.height, screenshot.width, 3
            )
        largest_side = max(image.shape[:2])
        if largest_side > MAX_OCR_IMAGE_SIDE:
            scale = MAX_OCR_IMAGE_SIDE / largest_side
            resized_width = max(1, int(image.shape[1] * scale))
            resized_height = max(1, int(image.shape[0] * scale))
            image = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_AREA)
        global _reader
        if _reader is None:
            _reader = easyocr.Reader(["en"], gpu=False)
        text = "\n".join(
            line for line in _reader.readtext(image, detail=0, canvas_size=MAX_OCR_IMAGE_SIDE, mag_ratio=1.0)
            if line
        ).strip()
    except Exception as exc:
        return f"Failed to read screen: {exc}"

    if not text:
        return "No readable text found on screen."
    if len(text) > MAX_SCREEN_TEXT_CHARS:
        marker = "\n[Text truncated.]"
        text = text[: MAX_SCREEN_TEXT_CHARS - len(marker)].rstrip() + marker
    return text