"""System automation skill helpers using psutil and OS utilities."""

import os
import subprocess
import sys
from typing import Dict

import psutil


def open_application(name: str) -> str:
    """Open a named application on the system."""
    if not name:
        return "No application name provided."

    try:
        if os.name == "nt":
            try:
                os.startfile(name)
            except OSError:
                subprocess.Popen(["cmd", "/c", "start", "", name], shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", name])
        else:
            subprocess.Popen([name])
        return f"Opened application: {name}"
    except Exception as exc:
        return f"Failed to open application: {exc}"


def close_application(name: str) -> str:
    """Close a named application process if it is running."""
    if not name:
        return "No application name provided."

    closed = 0
    for proc in psutil.process_iter(["name", "exe", "cmdline"]):
        try:
            proc_name = proc.info.get("name") or ""
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if name.lower() in proc_name.lower() or name.lower() in cmdline.lower():
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
