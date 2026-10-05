"""Vision skill helpers for webcam capture and reverse image search."""

from pathlib import Path


def capture_photo(filename: str = "capture.jpg") -> str:
    """Capture a photo from the webcam and save it to the given filename."""
    try:
        import cv2
    except ImportError as exc:
        return "OpenCV is not installed. Install with `pip install opencv-python`."

    path = Path(filename)
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
                camera = cv2.VideoCapture(camera_index)
                if not camera.isOpened():
                    errors.append(f"camera index {camera_index}: OpenCV could not open the device")
                    continue
                ret, frame = camera.read()
                if ret and frame is not None:
                    captured_frame = frame
                    break
                errors.append(f"camera index {camera_index}: OpenCV opened the device but returned no frame")
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

    path.parent.mkdir(parents=True, exist_ok=True)
    success = cv2.imwrite(str(path), captured_frame)
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
