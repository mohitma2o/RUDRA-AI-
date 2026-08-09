"""Vision skill helpers for webcam capture and reverse image search."""

from pathlib import Path
from typing import Optional


def capture_photo(filename: str = "capture.jpg") -> str:
    """Capture a photo from the webcam and save it to the given filename."""
    try:
        import cv2
    except ImportError as exc:
        return "OpenCV is not installed. Install with `pip install opencv-python`."

    path = Path(filename)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return "Unable to open webcam."

    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return "Failed to capture image from webcam."

    path.parent.mkdir(parents=True, exist_ok=True)
    success = cv2.imwrite(str(path), frame)
    if not success:
        return "Failed to save captured image."
    return f"Captured photo to {path.resolve()}"


def reverse_image_search(filename: str) -> str:
    """Open Google Lens and execute a reverse image search for the saved image."""
    target = Path(filename)
    if not target.exists():
        return f"Image file not found: {filename}"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "Playwright is not installed. Install with `pip install playwright`."

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto("https://lens.google.com/upload")
            page.wait_for_timeout(2000)

            file_input = page.query_selector('input[type="file"]')
            if not file_input:
                browser.close()
                return "Could not locate Google Lens upload field."

            file_input.set_input_files(str(target.resolve()))
            page.wait_for_timeout(5000)
            upload_url = page.url
            browser.close()
            return f"Opened Google Lens for image search: {upload_url}"
    except Exception as exc:
        return f"Reverse image search failed: {exc}"
