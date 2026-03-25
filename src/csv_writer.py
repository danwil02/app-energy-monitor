"""CSV writer for storing energy metrics."""

import csv
from pathlib import Path
from typing import List, Optional
from .models import ProcessMetric, SystemPowerSample
from .logger import get_logger

logger = get_logger()


class CSVWriter:
    """Write energy metrics to CSV files."""

    # CSV headers for process metrics
    PROCESS_HEADERS = [
        'timestamp', 'pid', 'app_name', 'cpu_user_ms', 'cpu_system_ms',
        'memory_rss_mb', 'memory_vms_mb', 'io_read_count', 'io_write_count',
        'io_read_bytes', 'io_write_bytes', 'num_threads', 'num_fds',
        'estimated_energy_mah', 'estimated_power_mw'
    ]

    # CSV headers for system power metrics
    SYSTEM_HEADERS = [
        'timestamp', 'total_system_power_mw', 'cpu_power_mw', 'gpu_power_mw',
        'system_memory_power_mw', 'total_package_idle_exits', 'total_platform_timer_wakeups'
    ]

    def __init__(self, csv_path: Path = None, system_power_path: Path = None):
        """Initialize CSV writer.

        Args:
            csv_path: Path to write process metrics CSV (default: data/energy_log.csv)
            system_power_path: Path to write system power CSV (default: data/system_power.csv)
        """
        self.csv_path = csv_path or Path("data/energy_log.csv")
        self.system_power_path = system_power_path or Path("data/system_power.csv")

        # Ensure directories exist
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self.system_power_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize files with headers if they don't exist
        self._ensure_headers()

    def _ensure_headers(self):
        """Ensure CSV files exist with headers."""
        # Process metrics CSV
        if not self.csv_path.exists():
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.PROCESS_HEADERS)
                writer.writeheader()
            logger.debug(f"Created CSV file: {self.csv_path}")

        # System power CSV
        if not self.system_power_path.exists():
            with open(self.system_power_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.SYSTEM_HEADERS)
                writer.writeheader()
            logger.debug(f"Created system power CSV: {self.system_power_path}")

    def write_metrics(self, metrics: List[ProcessMetric]) -> int:
        """Append process metrics to CSV.

        Args:
            metrics: List of ProcessMetric objects

        Returns:
            Number of rows written
        """
        if not metrics:
            return 0

        try:
            with open(self.csv_path, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.PROCESS_HEADERS)
                for metric in metrics:
                    writer.writerow(metric.to_dict())

            logger.debug(f"Wrote {len(metrics)} process metrics to {self.csv_path}")
            return len(metrics)

        except Exception as e:
            logger.error(f"Failed to write CSV: {e}")
            return 0

    def write_system_power(self, power_sample: SystemPowerSample) -> bool:
        """Append system power metrics to CSV.

        Args:
            power_sample: SystemPowerSample object

        Returns:
            True if successful, False otherwise
        """
        if not power_sample:
            return False

        try:
            with open(self.system_power_path, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.SYSTEM_HEADERS)
                writer.writerow(power_sample.to_dict())

            logger.debug(f"Wrote system power metrics to {self.system_power_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to write system power CSV: {e}")
            return False

    def get_file_size_mb(self) -> float:
        """Get current CSV file size in MB."""
        if self.csv_path.exists():
            return self.csv_path.stat().st_size / (1024 * 1024)
        return 0.0

    def get_row_count(self) -> int:
        """Get number of data rows in CSV (excluding header)."""
        if not self.csv_path.exists():
            return 0

        try:
            with open(self.csv_path, 'r') as f:
                return sum(1 for _ in f) - 1  # Subtract 1 for header
        except Exception as e:
            logger.error(f"Failed to count CSV rows: {e}")
            return 0
