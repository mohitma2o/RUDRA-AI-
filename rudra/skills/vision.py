"""Vision skill helpers for webcam capture and reverse image search."""

from datetime import datetime
from pathlib import Path
import sys
import time

_PHOTO_DIR = Path.home() / "Pictures" / "Rudra"


def _is_usable_frame(frame) -> bool:
    try:
        return frame is not None and int(frame.size) > 0 and float(frame.mean()) > 4.0
    except (AttributeError, TypeError, ValueError):
        return False


def capture_photo(filename: str | None = None) -> str:
    """Capture a photo from the webcam and save it to ~/Pictures/Rudra/."""
    try:
        import cv2
    except ImportError:
        return "OpenCV is not installed. Install with `pip install opencv-python`."

    _PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    if filename:
        path = _PHOTO_DIR / filename
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = _PHOTO_DIR / f"rudra_{timestamp}.jpg"
    errors = []
    opencv_errors = []
    captured_frame = None

    def record_opencv_error(status, function_name, message, filename, line):
        diagnostic = f"{function_name}: {message} (status={status}, line={line})"
        opencv_errors.append(diagnostic)
        print(f"OpenCV camera error: {diagnostic}")
        return 0

    previous_error_handler = cv2.redirectError(record_opencv_error)
    try:
        for camera_index in (0, 1, 2):
            camera = None
            try:
                if sys.platform == "win32":
                    camera = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
                else:
                    camera = cv2.VideoCapture(camera_index)
                if not camera.isOpened():
                    errors.append(f"camera index {camera_index}: OpenCV could not open the device")
                    continue
                warmup_failures = 0
                for _ in range(20):
                    ret, frame = camera.read()
                    if not ret or frame is None:
                        warmup_failures += 1
                    time.sleep(0.03)
                dark_frames = 0
                failed_reads = 0
                for _ in range(5):
                    ret, frame = camera.read()
                    if not ret or frame is None:
                        failed_reads += 1
                    elif not _is_usable_frame(frame):
                        dark_frames += 1
                    else:
                        captured_frame = frame
                        break
                    time.sleep(0.03)
                if captured_frame is not None:
                    break
                errors.append(
                    f"camera index {camera_index}: no usable frame after 20 warm-up frames "
                    f"({warmup_failures} warm-up reads failed, {failed_reads} capture reads "
                    f"failed, {dark_frames} nearly-black frames)"
                )
            except Exception as exc:
                errors.append(f"camera index {camera_index}: {type(exc).__name__}: {exc}")
            finally:
                if camera is not None:
                    camera.release()
    finally:
        cv2.redirectError(previous_error_handler)

    if captured_frame is None:
        details = "; ".join(opencv_errors + errors)
        if not opencv_errors:
            details = f"OpenCV emitted no native diagnostic; {details}"
        return (
            f"Unable to capture from webcams at indices 0, 1, or 2. OpenCV details: {details}. "
            "If Windows privacy is blocking access, check Settings > Privacy & Security > Camera > "
            '"Let desktop apps access your camera" and turn it ON.'
        )

    try:
        success = cv2.imwrite(str(path), captured_frame)
    except Exception as exc:
        return f"Failed to save captured image: {type(exc).__name__}: {exc}"
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
