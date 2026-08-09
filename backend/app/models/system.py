"""
RUDRA AI - Pydantic Models for System Monitor
Request/Response schemas for system monitoring.
"""

from pydantic import BaseModel
from typing import Optional


class CpuStats(BaseModel):
    """CPU usage statistics."""
    percent: float
    count: int
    frequency_mhz: Optional[float] = None
    per_core: list[float] = []


class MemoryStats(BaseModel):
    """Memory usage statistics."""
    total_gb: float
    used_gb: float
    available_gb: float
    percent: float


class DiskStats(BaseModel):
    """Disk usage statistics."""
    total_gb: float
    used_gb: float
    free_gb: float
    percent: float
    partitions: list[dict] = []


class BatteryStats(BaseModel):
    """Battery status."""
    percent: Optional[float] = None
    plugged: Optional[bool] = None
    time_left: Optional[str] = None


class NetworkStats(BaseModel):
    """Network I/O statistics."""
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int


class ProcessInfo(BaseModel):
    """Information about a running process."""
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    status: str


class SystemStats(BaseModel):
    """Complete system statistics snapshot."""
    cpu: CpuStats
    memory: MemoryStats
    disk: DiskStats
    battery: Optional[BatteryStats] = None
    network: NetworkStats
    uptime_hours: float
    top_processes: list[ProcessInfo] = []
