"""InfluxDB writer for storing energy metrics in time-series database."""

from datetime import datetime
from typing import List, Optional
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS, Point

from .models import ProcessMetric, SystemPowerSample
from .logger import get_logger

logger = get_logger()


class InfluxDBWriter:
    """Write energy metrics to InfluxDB."""

    def __init__(self, url: str, org: str, bucket: str, token: str):
        """Initialize InfluxDB writer.

        Args:
            url: InfluxDB server URL (e.g., http://localhost:8086)
            org: InfluxDB organization
            bucket: InfluxDB bucket name
            token: InfluxDB API token
        """
        self.url = url
        self.org = org
        self.bucket = bucket
        self.token = token
        self.client: Optional[InfluxDBClient] = None
        self.write_api = None
        self._connect()

    def _connect(self) -> bool:
        """Establish connection to InfluxDB.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.client = InfluxDBClient(
                url=self.url,
                org=self.org,
                token=self.token
            )

            # Test connection by calling ping
            self.client.ping()
            self.write_api = self.client.write_api(write_type=SYNCHRONOUS)
            logger.info(f"Connected to InfluxDB at {self.url}")
            return True

        except Exception as e:
            logger.warning(f"Failed to connect to InfluxDB: {e}")
            self.client = None
            return False

    def write_metrics(self, metrics: List[ProcessMetric]) -> int:
        """Write process metrics to InfluxDB.

        Args:
            metrics: List of ProcessMetric objects

        Returns:
            Number of metrics written
        """
        if not self.client or not self.write_api:
            logger.warning("InfluxDB not connected, skipping write")
            return 0

        if not metrics:
            return 0

        try:
            points = []
            for metric in metrics:
                point = (
                    Point("app_energy")
                    .tag("app_name", metric.app_name)
                    .tag("pid", metric.pid)
                    .field("cpu_user_ms", metric.cpu_user_ms)
                    .field("cpu_system_ms", metric.cpu_system_ms)
                    .field("memory_rss_mb", metric.memory_rss_mb)
                    .field("memory_vms_mb", metric.memory_vms_mb)
                    .field("io_read_count", metric.io_read_count)
                    .field("io_write_count", metric.io_write_count)
                    .field("io_read_bytes", metric.io_read_bytes)
                    .field("io_write_bytes", metric.io_write_bytes)
                    .field("num_threads", metric.num_threads)
                    .field("num_fds", metric.num_fds)
                    .field("estimated_energy_mah", metric.estimated_energy_mah)
                    .field("estimated_power_mw", metric.estimated_power_mw)
                    .time(metric.timestamp)
                )
                points.append(point)

            self.write_api.write(bucket=self.bucket, org=self.org, records=points)
            logger.debug(f"Wrote {len(metrics)} process metrics to InfluxDB")
            return len(metrics)

        except Exception as e:
            logger.error(f"Failed to write metrics to InfluxDB: {e}")
            # Try to reconnect
            self._connect()
            return 0

    def write_system_power(self, power_sample: SystemPowerSample) -> bool:
        """Write system power metrics to InfluxDB.

        Args:
            power_sample: SystemPowerSample object

        Returns:
            True if successful, False otherwise
        """
        if not self.client or not self.write_api:
            logger.warning("InfluxDB not connected, skipping write")
            return False

        if not power_sample:
            return False

        try:
            point = (
                Point("system_power")
                .field("total_system_power_mw", power_sample.total_system_power_mw)
                .field("cpu_power_mw", power_sample.cpu_power_mw)
                .field("gpu_power_mw", power_sample.gpu_power_mw)
                .field("system_memory_power_mw", power_sample.system_memory_power_mw)
                .field("total_package_idle_exits", power_sample.total_package_idle_exits)
                .field("total_platform_timer_wakeups", power_sample.total_platform_timer_wakeups)
                .time(power_sample.timestamp)
            )

            self.write_api.write(bucket=self.bucket, org=self.org, records=point)
            logger.debug("Wrote system power metrics to InfluxDB")
            return True

        except Exception as e:
            logger.error(f"Failed to write system power to InfluxDB: {e}")
            # Try to reconnect
            self._connect()
            return False

    def close(self):
        """Close connection to InfluxDB."""
        if self.client:
            self.client.close()
            logger.debug("Closed InfluxDB connection")
