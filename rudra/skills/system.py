import difflib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Dict, List, Optional, Set

import psutil

# URI-scheme entries (ends with ":") are opened via os.startfile() to reach
# Store / system apps that are not plain executables on PATH.
APP_COMMAND_MAP = {
    "notepad": "notepad.exe",
    "calculator": "calc",
    "calc": "calc",
    "file explorer": "explorer",
    "explorer": "explorer",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "terminal": "wt",
    "windows terminal": "wt",
    "powershell": "powershell.exe",
    "paint": "mspaint.exe",
    "task manager": "taskmgr.exe",
    # Windows Camera is a Store app — open via URI, not as a filename
    "camera": "microsoft.windows.camera:",
    "camera app": "microsoft.windows.camera:",
    "windows camera": "microsoft.windows.camera:",
    # Other common Store / URI apps
    "settings": "ms-settings:",
    "windows settings": "ms-settings:",
    "store": "ms-windows-store:",
    "microsoft store": "ms-windows-store:",
    "spotify": "spotify:",
    "whatsapp": "whatsapp:",
}

_INSTALLED_APPS_CACHE: Optional[List[Dict[str, str]]] = None


def _get_installed_apps(force_refresh: bool = False) -> List[Dict[str, str]]:
    """Retrieve installed Windows applications from Start Menu index (Get-StartApps)."""
    global _INSTALLED_APPS_CACHE
    if _INSTALLED_APPS_CACHE is not None and not force_refresh:
        return _INSTALLED_APPS_CACHE

    if os.name != "nt":
        _INSTALLED_APPS_CACHE = []
        return _INSTALLED_APPS_CACHE

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-StartApps | ConvertTo-Json -Depth 2"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            raw = json.loads(proc.stdout)
            if isinstance(raw, dict):
                raw = [raw]
            apps = [
                {"Name": str(item["Name"]).strip(), "AppID": str(item["AppID"]).strip()}
                for item in raw
                if isinstance(item, dict) and item.get("Name") and item.get("AppID")
            ]
            _INSTALLED_APPS_CACHE = apps
            return _INSTALLED_APPS_CACHE
    except Exception:
        pass

    if _INSTALLED_APPS_CACHE is None:
        _INSTALLED_APPS_CACHE = []
    return _INSTALLED_APPS_CACHE


_get_installed_apps()


def _match_app_in_list(query: str, apps: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Match a query string against a list of installed app objects."""
    normalized_query = query.strip().lower()
    if not normalized_query or not apps:
        return None

    # 1. Exact case-insensitive match
    for app in apps:
        if normalized_query == app["Name"].lower():
            return app

    # 2. Fuzzy closest match using difflib
    name_map = {app["Name"].lower(): app for app in apps}
    close_matches = difflib.get_close_matches(normalized_query, list(name_map.keys()), n=1, cutoff=0.6)
    if close_matches:
        return name_map[close_matches[0]]

    return None


def resolve_installed_app(name: str) -> Optional[Dict[str, str]]:
    """Resolve a spoken app name against Windows Start Menu apps (with cache & refresh)."""
    if not name:
        return None

    cleaned = name.strip().lower()
    if cleaned.startswith("the "):
        cleaned = cleaned[4:].strip()

    # Try cached list first
    cached_apps = _get_installed_apps(force_refresh=False)
    matched = _match_app_in_list(cleaned, cached_apps)
    if matched:
        return matched

    # Re-run PowerShell refresh in case it was installed after startup
    refreshed_apps = _get_installed_apps(force_refresh=True)
    return _match_app_in_list(cleaned, refreshed_apps)


def _resolve_command(name: str) -> str:
    """Map a spoken app name to the real Windows executable command when needed."""
    if not name:
        return ""

    normalized = name.strip().lower()
    return APP_COMMAND_MAP.get(normalized, name)


def _get_process_match_stems(name: str, command: str) -> Set[str]:
    """Return process name stems to look for when verifying or closing apps."""
    stems = {name.lower().strip(), command.lower().strip()}
    if command.lower().endswith(".exe"):
        stems.add(command.lower()[:-4])
    if "chrome" in name.lower():
        stems.add("chrome")
    if "edge" in name.lower():
        stems.add("msedge")
    if "calc" in name.lower() or "calculator" in name.lower():
        stems.add("calc")
        stems.add("calculator")
    if "camera" in name.lower():
        stems.add("camera")
        stems.add("windowscamera")
    if "settings" in name.lower():
        stems.add("systemsettings")
        stems.add("settings")
    if "terminal" in name.lower() or "wt" in name.lower():
        stems.add("wt")
        stems.add("windowsterminal")
    if "word" in name.lower():
        stems.add("winword")
    if "paint" in name.lower():
        stems.add("mspaint")
    if "task manager" in name.lower() or "taskmgr" in name.lower():
        stems.add("taskmgr")
    return {s for s in stems if s}


def _resolve_registered_exe_path(command: str) -> Optional[str]:
    """Find the full executable path via PATH or Windows App Paths registry."""
    which_path = shutil.which(command)
    if which_path:
        return which_path

    if os.name == "nt":
        try:
            import winreg

            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                subkeys = [
                    rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{command}",
                ]
                if not command.lower().endswith(".exe"):
                    subkeys.append(rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{command}.exe")
                for subkey in subkeys:
                    try:
                        with winreg.OpenKey(root, subkey) as key:
                            val, _ = winreg.QueryValueEx(key, "")
                            if val and os.path.exists(val):
                                return val
                    except OSError:
                        continue
        except Exception:
            pass

    return None


def open_application(name: str, timeout: float = 3.0) -> str:
    """Open a named application on the system via fast-path or dynamic Start Menu resolution."""
    if not name:
        return "No application name provided."

    normalized = name.strip().lower()

    # 1. Fast-path cache for known common apps
    fast_command = APP_COMMAND_MAP.get(normalized)
    resolved_app: Optional[Dict[str, str]] = None
    if not fast_command:
        # 2. Dynamic Start Menu resolution
        resolved_app = resolve_installed_app(name)

    if not fast_command and not resolved_app:
        return f"Failed to open '{name}'. Application not found."

    display_name = resolved_app["Name"] if resolved_app else name
    appid = resolved_app.get("AppID", "") if resolved_app else ""
    is_uwp = "!" in appid

    stems = _get_process_match_stems(display_name, fast_command or appid)
    if resolved_app:
        if appid.endswith(".exe"):
            stems.add(Path(appid).name.lower())
            stems.add(Path(appid).stem.lower())
        for word in display_name.lower().split():
            if len(word) >= 3 and word not in {"the", "app", "application"}:
                stems.add(word)

    existing_pids: Set[int] = set()
    try:
        existing_pids = {p.pid for p in psutil.process_iter(["pid"])}
    except Exception:
        pass

    spawned_proc: Optional[subprocess.Popen] = None
    try:
        if os.name == "nt":
            if resolved_app and is_uwp:
                # UWP format (PackageFamilyName!AppId)
                spawned_proc = subprocess.Popen(["explorer.exe", f"shell:appsFolder\\{appid}"])
            elif resolved_app and os.path.exists(appid):
                try:
                    spawned_proc = subprocess.Popen([appid])
                except OSError:
                    os.startfile(appid)
            elif resolved_app and appid.startswith("{"):
                spawned_proc = subprocess.Popen(["explorer.exe", f"shell:appsFolder\\{appid}"])
            elif fast_command:
                # URI-scheme entries (e.g. "microsoft.windows.camera:") must use
                # os.startfile — subprocess cannot handle protocol handlers.
                if fast_command.endswith(":"):
                    try:
                        os.startfile(fast_command)
                        return f"Opening {display_name} now."
                    except Exception as uri_exc:
                        return f"Failed to open '{name}': {uri_exc}"
                exe_path = _resolve_registered_exe_path(fast_command)
                if exe_path:
                    try:
                        spawned_proc = subprocess.Popen([exe_path])
                    except Exception:
                        pass
                if spawned_proc is None:
                    try:
                        os.startfile(fast_command)
                    except OSError:
                        pass
                if spawned_proc is None:
                    try:
                        spawned_proc = subprocess.Popen(f'start "" "{fast_command}"', shell=True)
                    except Exception:
                        pass
                if spawned_proc is None:
                    try:
                        spawned_proc = subprocess.Popen(fast_command, shell=True)
                    except Exception:
                        pass
            else:
                target_cmd = appid or name
                exe_path = _resolve_registered_exe_path(target_cmd)
                if exe_path:
                    try:
                        spawned_proc = subprocess.Popen([exe_path])
                    except Exception:
                        pass
                if spawned_proc is None:
                    try:
                        os.startfile(target_cmd)
                    except OSError:
                        spawned_proc = subprocess.Popen(["explorer.exe", f"shell:appsFolder\\{target_cmd}"])
        elif sys.platform == "darwin":
            spawned_proc = subprocess.Popen(["open", "-a", display_name])
        else:
            spawned_proc = subprocess.Popen([display_name])
    except Exception as exc:
        return f"Failed to open '{name}': {exc}"

    # Verify the app actually launched
    start_time = time.time()
    poll_interval = 0.15
    while time.time() - start_time < timeout:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.pid not in existing_pids:
                    pname = (proc.info.get("name") or "").lower()
                    if any(stem in pname or pname.startswith(stem) for stem in stems):
                        return f"Opening {display_name} now."
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        time.sleep(poll_interval)

    # Check if a matching process was already running
    for proc in psutil.process_iter(["name"]):
        try:
            pname = (proc.info.get("name") or "").lower()
            if any(stem in pname or pname.startswith(stem) for stem in stems):
                return f"Opening {display_name} now."
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # UWP / dynamic app optimistic reporting rule:
    # Some UWP apps (e.g. Camera, Settings) spawn under host wrappers or are slow to spawn
    if is_uwp or (resolved_app and not fast_command):
        return f"Opening {display_name} now."

    if spawned_proc is not None:
        try:
            if spawned_proc.poll() is None:
                spawned_proc.terminate()
                spawned_proc.wait(timeout=0.2)
        except Exception:
            pass

    return f"Failed to open '{name}'. Application did not start."


def close_application(name: str) -> str:
    """Close a named application process if it is running."""
    if not name:
        return "No application name provided."

    command = _resolve_command(name)
    stems = _get_process_match_stems(name, command)

    closed = 0
    for proc in psutil.process_iter(["name", "exe", "cmdline"]):
        try:
            proc_name = (proc.info.get("name") or "").lower()
            cmdline = " ".join(proc.info.get("cmdline") or []).lower()
            if any(stem in proc_name or stem in cmdline for stem in stems):
                proc.terminate()
                closed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if closed:
        return f"Closed {closed} process(es) matching '{name}'."
    return f"No running process matched '{name}'."


def get_system_stats() -> Dict[str, object]:
    """Return a dictionary of system statistics for battery, RAM, and disk."""
    virtual = psutil.virtual_memory()
    disk = psutil.disk_usage("/") if os.name != "nt" else psutil.disk_usage("c:/")
    battery = psutil.sensors_battery()

    return {
        "cpu_percent": psutil.cpu_percent(interval=1.0),
        "cpu_count": psutil.cpu_count(logical=True),
        "memory_total_gb": round(virtual.total / 1024**3, 2),
        "memory_used_gb": round(virtual.used / 1024**3, 2),
        "memory_percent": virtual.percent,
        "disk_total_gb": round(disk.total / 1024**3, 2),
        "disk_used_gb": round(disk.used / 1024**3, 2),
        "disk_percent": disk.percent,
        "battery_percent": battery.percent if battery is not None else None,
        "battery_plugged": battery.power_plugged if battery is not None else None,
    }
