"""Collector module for gathering per-process metrics."""

from datetime import datetime
from typing import List
import psutil

from .models import ProcessMetric
from .logger import get_logger

logger = get_logger()


class MetricsCollector:
    """Collect process metrics from the system."""

    def __init__(self, app_whitelist: List[str] = None, app_blacklist: List[str] = None):
        """Initialize collector with optional filtering.

        Args:
            app_whitelist: List of app names to include (if set, only these are collected)
            app_blacklist: List of app names to exclude
        """
        self.app_whitelist = app_whitelist or []
        self.app_blacklist = app_blacklist or []

    def _should_collect(self, app_name: str) -> bool:
        """Check if an app should be collected based on filters."""
        # If whitelist is set, only collect whitelisted apps
        if self.app_whitelist:
            return any(wl.lower() in app_name.lower() for wl in self.app_whitelist)

        # Otherwise, exclude blacklisted apps
        if self.app_blacklist:
            return not any(bl.lower() in app_name.lower() for bl in self.app_blacklist)

        return True

    def collect_all(self) -> List[ProcessMetric]:
        """Collect metrics for all running processes.

        Returns:
            List of ProcessMetric objects
        """
        timestamp = datetime.now()
        metrics = []

        for proc in psutil.process_iter(['pid', 'name', 'cpu_times', 'memory_info',
                                         'num_threads', 'num_fds']):
            try:
                # Get process info
                pid = proc.pid
                app_name = proc.info['name'] or f"PID-{pid}"

                # Check filtering
                if not self._should_collect(app_name):
                    continue

                # Get CPU times
                cpu_times = proc.info.get('cpu_times')
                if not cpu_times:
                    continue

                cpu_user_ms = cpu_times.user * 1000  # Convert to ms
                cpu_system_ms = cpu_times.system * 1000

                # Get memory info
                memory_info = proc.info.get('memory_info')
                memory_rss_mb = (memory_info.rss / (1024 * 1024)) if memory_info else 0
                memory_vms_mb = (memory_info.vms / (1024 * 1024)) if memory_info else 0

                # Get I/O counters (may not be available on all systems)
                io_read_count = 0
                io_write_count = 0
                io_read_bytes = 0
                io_write_bytes = 0
                try:
                    io_counters = proc.io_counters()
                    io_read_count = io_counters.read_count
                    io_write_count = io_counters.write_count
                    io_read_bytes = io_counters.read_bytes
                    io_write_bytes = io_counters.write_bytes
                except (psutil.AccessDenied, AttributeError):
                    pass  # I/O counters not available

                # Get thread and file descriptor counts
                num_threads = proc.info.get('num_threads', 0)
                num_fds = proc.info.get('num_fds', 0)

                # Create metric
                metric = ProcessMetric(
                    timestamp=timestamp,
                    pid=pid,
                    app_name=app_name,
                    cpu_user_ms=cpu_user_ms,
                    cpu_system_ms=cpu_system_ms,
                    memory_rss_mb=memory_rss_mb,
                    memory_vms_mb=memory_vms_mb,
                    io_read_count=io_read_count,
                    io_write_count=io_write_count,
                    io_read_bytes=io_read_bytes,
                    io_write_bytes=io_write_bytes,
                    num_threads=num_threads,
                    num_fds=num_fds,
                )

                metrics.append(metric)

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process died or access denied, skip
                continue
            except Exception as e:
                logger.debug(f"Error collecting metrics for process: {e}")
                continue

        return metrics

    def collect_by_pid(self, pid: int) -> ProcessMetric:
        """Collect metrics for a specific process by PID.

        Args:
            pid: Process ID

        Returns:
            ProcessMetric object or None if process not found
        """
        try:
            proc = psutil.Process(pid)
            timestamp = datetime.now()

            # Get all info at once
            with proc.oneshot():
                app_name = proc.name()
                cpu_times = proc.cpu_times()
                memory_info = proc.memory_info()
                io_counters = proc.io_counters()
                num_threads = proc.num_threads()
                num_fds = proc.num_fds() if hasattr(proc, 'num_fds') else 0

            return ProcessMetric(
                timestamp=timestamp,
                pid=pid,
                app_name=app_name,
                cpu_user_ms=cpu_times.user * 1000,
                cpu_system_ms=cpu_times.system * 1000,
                memory_rss_mb=memory_info.rss / (1024 * 1024),
                memory_vms_mb=memory_info.vms / (1024 * 1024),
                io_read_count=io_counters.read_count,
                io_write_count=io_counters.write_count,
                io_read_bytes=io_counters.read_bytes,
                io_write_bytes=io_counters.write_bytes,
                num_threads=num_threads,
                num_fds=num_fds,
            )

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
