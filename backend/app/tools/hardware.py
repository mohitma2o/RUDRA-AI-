"""Hardware control tools: volume, brightness, lock, power, camera, screenshot."""

import asyncio
import ctypes
import datetime
import os
import sys
from pathlib import Path

from .registry import Tier, tool

# ---------------------------------------------------------------------------
# Audio / Volume (pycaw on Windows)
# ---------------------------------------------------------------------------

@tool("volume_set", "Set system volume to a percentage (0-100).",
      tier=Tier.AUTO,
      schema={"type": "object", "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}}, "required": ["level"]})
async def volume_set(level: int) -> str:
    def _set():
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            import comtypes
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMasterVolumeLevelScalar(max(0, min(1, level / 100)), None)
            return f"Volume set to {level}%."
        except Exception as e:
            return f"Volume control failed: {e}"
    return await asyncio.to_thread(_set)


@tool("volume_mute", "Toggle system audio mute.", tier=Tier.AUTO)
async def volume_mute() -> str:
    def _mute():
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            import comtypes
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
            vol = interface.QueryInterface(IAudioEndpointVolume)
            muted = vol.GetMute()
            vol.SetMute(not muted, None)
            return "Muted." if not muted else "Unmuted."
        except Exception as e:
            return f"Mute toggle failed: {e}"
    return await asyncio.to_thread(_mute)


@tool("media_control", "Control media playback (play/pause/next/prev).", tier=Tier.AUTO,
      schema={"type": "object", "properties": {"action": {"type": "string", "enum": ["play_pause", "next", "prev"]}}, "required": ["action"]})
async def media_control(action: str) -> str:
    def _press():
        try:
            import pyautogui
            key_map = {"play_pause": "playpause", "next": "nexttrack", "prev": "prevtrack"}
            key = key_map.get(action, "playpause")
            pyautogui.press(key)
            return f"Media key '{action}' pressed."
        except Exception as e:
            return f"Media control failed: {e}"
    return await asyncio.to_thread(_press)


# ---------------------------------------------------------------------------
# Display brightness (screen-brightness-control)
# ---------------------------------------------------------------------------

@tool("brightness_set", "Set screen brightness to a percentage (0-100).", tier=Tier.AUTO,
      schema={"type": "object", "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}}, "required": ["level"]})
async def brightness_set(level: int) -> str:
    def _set():
        try:
            import screen_brightness_control as sbc
            sbc.set_brightness(max(0, min(100, level)))
            return f"Brightness set to {level}%."
        except Exception as e:
            return f"Brightness control failed: {e}"
    return await asyncio.to_thread(_set)


@tool("brightness_up", "Increase screen brightness by 10%.", tier=Tier.AUTO)
async def brightness_up() -> str:
    def _up():
        try:
            import screen_brightness_control as sbc
            current = sbc.get_brightness()
            val = (current[0] if isinstance(current, list) else current) + 10
            sbc.set_brightness(min(100, val))
            return f"Brightness increased to {min(100, val)}%."
        except Exception as e:
            return f"Brightness up failed: {e}"
    return await asyncio.to_thread(_up)


@tool("brightness_down", "Decrease screen brightness by 10%.", tier=Tier.AUTO)
async def brightness_down() -> str:
    def _down():
        try:
            import screen_brightness_control as sbc
            current = sbc.get_brightness()
            val = (current[0] if isinstance(current, list) else current) - 10
            sbc.set_brightness(max(0, val))
            return f"Brightness decreased to {max(0, val)}%."
        except Exception as e:
            return f"Brightness down failed: {e}"
    return await asyncio.to_thread(_down)


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------

@tool("system_status", "Get battery, CPU, RAM, and disk status.", tier=Tier.AUTO)
async def system_status() -> str:
    def _stats():
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("c:/" if sys.platform == "win32" else "/")
            bat = psutil.sensors_battery()
            parts = [
                f"CPU {cpu:.0f}%",
                f"RAM {mem.percent:.0f}% ({mem.used // (1024**3):.1f}/{mem.total // (1024**3):.1f} GB)",
                f"Disk {disk.percent:.0f}%",
            ]
            if bat:
                plug = "plugged in" if bat.power_plugged else "on battery"
                parts.append(f"Battery {bat.percent:.0f}% ({plug})")
            return ", ".join(parts) + "."
        except Exception as e:
            return f"Status check failed: {e}"
    return await asyncio.to_thread(_stats)


@tool("get_time", "Get the current time and date.", tier=Tier.AUTO)
async def get_time() -> str:
    now = datetime.datetime.now()
    return now.strftime("It is %I:%M %p on %A, %B %d, %Y.")


# ---------------------------------------------------------------------------
# Screen / clipboard
# ---------------------------------------------------------------------------

@tool("screenshot", "Take a screenshot and save it to Pictures/Rudra.", tier=Tier.AUTO)
async def screenshot() -> str:
    def _snap():
        try:
            import mss, mss.tools
            save_dir = Path.home() / "Pictures" / "Rudra"
            save_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = save_dir / f"screenshot_{ts}.png"
            with mss.mss() as sc:
                monitor = sc.monitors[0]
                shot = sc.grab(monitor)
                mss.tools.to_png(shot.rgb, shot.size, output=str(out_path))
            return f"Screenshot saved to {out_path}."
        except Exception as e:
            return f"Screenshot failed: {e}"
    return await asyncio.to_thread(_snap)


# ---------------------------------------------------------------------------
# Lock screen / Power (CONFIRM for anything destructive)
# ---------------------------------------------------------------------------

@tool("lock_screen", "Lock the Windows session.", tier=Tier.AUTO)
async def lock_screen() -> str:
    def _lock():
        if sys.platform != "win32":
            return "Lock screen is only supported on Windows."
        ctypes.windll.user32.LockWorkStation()
        return "Screen locked."
    return await asyncio.to_thread(_lock)


@tool("sleep", "Put the computer to sleep.", tier=Tier.CONFIRM,
      schema={"type": "object", "properties": {}})
async def sleep_computer() -> str:
    def _sleep():
        if sys.platform == "win32":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return "Sleeping now."
        return "Sleep is only supported on Windows."
    return await asyncio.to_thread(_sleep)


@tool("shutdown", "Shut down the computer.", tier=Tier.CONFIRM,
      schema={"type": "object", "properties": {"delay_seconds": {"type": "integer"}}})
async def shutdown_computer(delay_seconds: int = 30) -> str:
    def _shutdown():
        if sys.platform == "win32":
            os.system(f"shutdown /s /t {delay_seconds}")
            return f"Shutting down in {delay_seconds} seconds. Say 'cancel shutdown' to abort."
        return "Shutdown is only supported on Windows."
    return await asyncio.to_thread(_shutdown)


@tool("restart", "Restart the computer.", tier=Tier.CONFIRM,
      schema={"type": "object", "properties": {"delay_seconds": {"type": "integer"}}})
async def restart_computer(delay_seconds: int = 30) -> str:
    def _restart():
        if sys.platform == "win32":
            os.system(f"shutdown /r /t {delay_seconds}")
            return f"Restarting in {delay_seconds} seconds. Say 'cancel restart' to abort."
        return "Restart is only supported on Windows."
    return await asyncio.to_thread(_restart)


@tool("cancel_shutdown", "Cancel a pending shutdown or restart.", tier=Tier.AUTO)
async def cancel_shutdown() -> str:
    def _cancel():
        if sys.platform == "win32":
            os.system("shutdown /a")
            return "Shutdown/restart cancelled."
        return "Only supported on Windows."
    return await asyncio.to_thread(_cancel)
