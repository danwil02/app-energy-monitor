"""Data models for energy metrics."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ProcessMetric:
    """Metrics for a single process at a point in time."""

    timestamp: datetime
    pid: int
    app_name: str
    cpu_user_ms: float  # User CPU time in milliseconds
    cpu_system_ms: float  # System CPU time in milliseconds
    memory_rss_mb: float  # Resident Set Size in MB
    memory_vms_mb: float  # Virtual Memory Size in MB
    io_read_count: int  # Number of read operations
    io_write_count: int  # Number of write operations
    io_read_bytes: int  # Bytes read
    io_write_bytes: int  # Bytes written
    num_threads: int  # Number of threads
    num_fds: int  # Number of file descriptors (Unix)

    # Estimated energy metrics (calculated from system correlation)
    estimated_energy_mah: float = 0.0  # Milliamp-hours
    estimated_power_mw: float = 0.0  # Milliwatts (energy / interval)

    def to_dict(self) -> dict:
        """Convert to dictionary for CSV/JSON export."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'pid': self.pid,
            'app_name': self.app_name,
            'cpu_user_ms': round(self.cpu_user_ms, 2),
            'cpu_system_ms': round(self.cpu_system_ms, 2),
            'memory_rss_mb': round(self.memory_rss_mb, 2),
            'memory_vms_mb': round(self.memory_vms_mb, 2),
            'io_read_count': self.io_read_count,
            'io_write_count': self.io_write_count,
            'io_read_bytes': self.io_read_bytes,
            'io_write_bytes': self.io_write_bytes,
            'num_threads': self.num_threads,
            'num_fds': self.num_fds,
            'estimated_energy_mah': round(self.estimated_energy_mah, 4),
            'estimated_power_mw': round(self.estimated_power_mw, 2),
        }


@dataclass
class SystemPowerSample:
    """System-level power metrics from powermetrics."""

    timestamp: datetime
    total_system_power_mw: float  # Total system power in milliwatts
    cpu_power_mw: float  # CPU power in milliwatts
    gpu_power_mw: float  # GPU power in milliwatts
    system_memory_power_mw: float  # Memory power in milliwatts
    total_package_idle_exits: int  # Total package idle exits
    total_platform_timer_wakeups: int  # Total platform timer wakeups

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'total_system_power_mw': round(self.total_system_power_mw, 2),
            'cpu_power_mw': round(self.cpu_power_mw, 2),
            'gpu_power_mw': round(self.gpu_power_mw, 2),
            'system_memory_power_mw': round(self.system_memory_power_mw, 2),
            'total_package_idle_exits': self.total_package_idle_exits,
            'total_platform_timer_wakeups': self.total_platform_timer_wakeups,
        }
