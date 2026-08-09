"""
RUDRA AI - System Monitor Service
Real-time system monitoring using psutil.
"""

import psutil
import platform
import time
import logging
from datetime import datetime

from app.models.system import (
    CpuStats, MemoryStats, DiskStats, BatteryStats,
    NetworkStats, ProcessInfo, SystemStats
)

logger = logging.getLogger(__name__)


class SystemService:
    """Service for monitoring system resources."""

    def __init__(self):
        self._boot_time = psutil.boot_time()

    def get_cpu_stats(self) -> CpuStats:
        """Get CPU usage statistics."""
        freq = psutil.cpu_freq()
        return CpuStats(
            percent=psutil.cpu_percent(interval=0.5),
            count=psutil.cpu_count(logical=True),
            frequency_mhz=round(freq.current, 1) if freq else None,
            per_core=psutil.cpu_percent(percpu=True),
        )

    def get_memory_stats(self) -> MemoryStats:
        """Get RAM usage statistics."""
        mem = psutil.virtual_memory()
        return MemoryStats(
            total_gb=round(mem.total / (1024 ** 3), 2),
            used_gb=round(mem.used / (1024 ** 3), 2),
            available_gb=round(mem.available / (1024 ** 3), 2),
            percent=mem.percent,
        )

    def get_disk_stats(self) -> DiskStats:
        """Get disk usage for the main partition."""
        try:
            usage = psutil.disk_usage("C:\\")
            partitions = []
            for p in psutil.disk_partitions():
                try:
                    pu = psutil.disk_usage(p.mountpoint)
                    partitions.append({
                        "device": p.device,
                        "mountpoint": p.mountpoint,
                        "fstype": p.fstype,
                        "total_gb": round(pu.total / (1024 ** 3), 2),
                        "used_gb": round(pu.used / (1024 ** 3), 2),
                        "percent": pu.percent,
                    })
                except (PermissionError, OSError):
                    continue

            return DiskStats(
                total_gb=round(usage.total / (1024 ** 3), 2),
                used_gb=round(usage.used / (1024 ** 3), 2),
                free_gb=round(usage.free / (1024 ** 3), 2),
                percent=usage.percent,
                partitions=partitions,
            )
        except Exception as e:
            logger.error("Disk stats error: %s", e)
            return DiskStats(total_gb=0, used_gb=0, free_gb=0, percent=0)

    def get_battery_stats(self) -> BatteryStats | None:
        """Get battery status (if available)."""
        battery = psutil.sensors_battery()
        if battery is None:
            return None
        time_left = None
        if battery.secsleft > 0:
            hours = battery.secsleft // 3600
            minutes = (battery.secsleft % 3600) // 60
            time_left = f"{hours}h {minutes}m"
        return BatteryStats(
            percent=round(battery.percent, 1),
            plugged=battery.power_plugged,
            time_left=time_left,
        )

    def get_network_stats(self) -> NetworkStats:
        """Get network I/O counters."""
        net = psutil.net_io_counters()
        return NetworkStats(
            bytes_sent=net.bytes_sent,
            bytes_recv=net.bytes_recv,
            packets_sent=net.packets_sent,
            packets_recv=net.packets_recv,
        )

    def get_top_processes(self, limit: int = 10) -> list[ProcessInfo]:
        """Get top processes by CPU usage."""
        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
            try:
                info = proc.info
                processes.append(ProcessInfo(
                    pid=info["pid"],
                    name=info["name"] or "Unknown",
                    cpu_percent=info["cpu_percent"] or 0.0,
                    memory_percent=round(info["memory_percent"] or 0.0, 2),
                    status=info["status"] or "unknown",
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by CPU usage descending
        processes.sort(key=lambda p: p.cpu_percent, reverse=True)
        return processes[:limit]

    def get_system_stats(self) -> SystemStats:
        """Get a complete snapshot of system statistics."""
        uptime_seconds = time.time() - self._boot_time
        return SystemStats(
            cpu=self.get_cpu_stats(),
            memory=self.get_memory_stats(),
            disk=self.get_disk_stats(),
            battery=self.get_battery_stats(),
            network=self.get_network_stats(),
            uptime_hours=round(uptime_seconds / 3600, 2),
            top_processes=self.get_top_processes(),
        )


# Global service instance
system_service = SystemService()
