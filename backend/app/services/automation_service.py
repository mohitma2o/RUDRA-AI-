"""
RUDRA AI - Automation Service
Handles desktop automation: opening/closing apps, file operations, system controls.
"""

import subprocess
import os
import glob
import logging
import shutil
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class AutomationService:
    """Service for desktop automation tasks."""

    # ─── Application Control ─────────────────────────────────────────

    async def open_application(self, app_name: str) -> dict:
        """Open an application by name."""
        # Common Windows application mappings
        app_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "paint": "mspaint.exe",
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
            "powershell": "powershell.exe",
            "explorer": "explorer.exe",
            "task manager": "taskmgr.exe",
            "control panel": "control.exe",
            "settings": "ms-settings:",
            "chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "edge": "msedge.exe",
            "vscode": "code",
            "vs code": "code",
            "word": "WINWORD.EXE",
            "excel": "EXCEL.EXE",
            "powerpoint": "POWERPNT.EXE",
            "outlook": "OUTLOOK.EXE",
        }

        app_lower = app_name.lower().strip()
        executable = app_map.get(app_lower, app_name)

        try:
            if executable.startswith("ms-"):
                os.startfile(executable)
            else:
                subprocess.Popen(
                    executable,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return {"status": "success", "message": f"Opened {app_name}"}
        except Exception as e:
            logger.error("Failed to open %s: %s", app_name, e)
            return {"status": "error", "message": f"Failed to open {app_name}: {str(e)}"}

    async def close_application(self, app_name: str) -> dict:
        """Close an application by name."""
        try:
            result = subprocess.run(
                ["taskkill", "/IM", f"{app_name}*", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return {"status": "success", "message": f"Closed {app_name}"}
            else:
                return {"status": "error", "message": f"Could not close {app_name}: {result.stderr}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ─── File Operations ─────────────────────────────────────────────

    async def search_files(
        self, query: str, directory: str = None, max_results: int = 20
    ) -> dict:
        """Search for files matching a pattern."""
        search_dir = directory or os.path.expanduser("~")
        results = []

        try:
            for root, dirs, files in os.walk(search_dir):
                # Skip hidden/system directories
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in [
                    "$Recycle.Bin", "AppData", "node_modules", "__pycache__", ".git"
                ]]

                for file in files:
                    if query.lower() in file.lower():
                        filepath = os.path.join(root, file)
                        try:
                            stat = os.stat(filepath)
                            results.append({
                                "name": file,
                                "path": filepath,
                                "size_kb": round(stat.st_size / 1024, 2),
                                "modified": str(stat.st_mtime),
                            })
                        except OSError:
                            continue

                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break

            return {"status": "success", "count": len(results), "results": results}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def create_folder(self, path: str) -> dict:
        """Create a new folder."""
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return {"status": "success", "message": f"Created folder: {path}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def rename_file(self, old_path: str, new_name: str) -> dict:
        """Rename a file or folder."""
        try:
            old = Path(old_path)
            new_path = old.parent / new_name
            old.rename(new_path)
            return {"status": "success", "message": f"Renamed to {new_name}", "new_path": str(new_path)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ─── System Controls ─────────────────────────────────────────────

    async def take_screenshot(self, save_path: Optional[str] = None) -> dict:
        """Take a screenshot of the current screen."""
        try:
            import pyautogui
            from app.config import settings

            if save_path is None:
                filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                save_path = str(settings.SCREENSHOTS_DIR / filename)

            screenshot = pyautogui.screenshot()
            screenshot.save(save_path)
            return {"status": "success", "path": save_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def capture_camera_photo(self, filename: Optional[str] = None) -> dict:
        """Capture a photo from the default camera."""
        try:
            import cv2
            from app.config import settings

            if filename:
                filename = filename.strip()
            if not filename:
                filename = f"camera_photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

            save_path = str(settings.SCREENSHOTS_DIR / filename)
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return {"status": "error", "message": "Unable to open camera."}

            ret, frame = cap.read()
            cap.release()
            if not ret or frame is None:
                return {"status": "error", "message": "Failed to capture camera image."}

            cv2.imwrite(save_path, frame)
            return {"status": "success", "path": save_path}
        except ImportError:
            return {"status": "error", "message": "OpenCV is not installed. Install with: pip install opencv-python"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def search_person_from_photo(self, filename: Optional[str] = None) -> dict:
        """Capture a photo and open the browser to an image search page."""
        photo_result = await self.capture_camera_photo(filename)
        if photo_result.get("status") != "success":
            return photo_result

        image_path = photo_result["path"]
        try:
            search_urls = [
                "https://www.google.com/imghp",
                "https://www.bing.com/images/search"
            ]
            for url in search_urls:
                webbrowser.open(url)

            return {
                "status": "success",
                "message": "Captured photo and opened image search pages. Upload the saved photo to perform person search.",
                "path": image_path,
                "search_urls": search_urls,
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "path": image_path}

    async def set_volume(self, level: int) -> dict:
        """Set system volume (0-100)."""
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))

            # Convert 0-100 to scalar (0.0-1.0)
            scalar = max(0.0, min(1.0, level / 100.0))
            volume.SetMasterVolumeLevelScalar(scalar, None)
            return {"status": "success", "volume": level}
        except ImportError:
            return {"status": "error", "message": "pycaw not installed. Install with: pip install pycaw"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Global service instance
automation_service = AutomationService()
