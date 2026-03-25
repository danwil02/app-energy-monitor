"""Energy estimation module for attributing system power to individual apps."""

from typing import List, Optional
from .models import ProcessMetric, SystemPowerSample
from .logger import get_logger

logger = get_logger()


class EnergyEstimator:
    """Estimate per-app energy consumption based on system power and process metrics."""

    # Battery capacity for macOS devices (mAh) - typical values
    MACBOOK_AIR_BATTERY_MAH = 49200  # ~100 Wh
    MACBOOK_PRO_BATTERY_MAH = 68200  # ~143 Wh
    MAC_MINI_BATTERY_MAH = 0  # Not applicable

    # Power estimation constants (tuned for macOS)
    CPU_TIME_WEIGHT = 0.6  # 60% of power attributed to CPU time
    MEMORY_WEIGHT = 0.1  # 10% to memory pressure
    IO_WEIGHT = 0.2  # 20% to I/O operations
    WAKEUP_WEIGHT = 0.1  # 10% to wakeups/interrupts

    def __init__(self, system_power_sample: Optional[SystemPowerSample] = None):
        """Initialize estimator with optional system power baseline.

        Args:
            system_power_sample: Current system power metrics (optional)
        """
        self.system_power = system_power_sample
        self.last_metrics = {}  # Track metrics between samples for delta calculations

    def estimate_energy(self, metrics: List[ProcessMetric],
                       interval_seconds: float = 60.0) -> List[ProcessMetric]:
        """Estimate energy for each process.

        Args:
            metrics: List of ProcessMetric objects
            interval_seconds: Time elapsed since last sample (for rate calculation)

        Returns:
            List of ProcessMetric objects with estimated_energy_mah and estimated_power_mw set
        """
        if not metrics:
            return metrics

        # Calculate total CPU time, memory, and I/O across all processes
        total_cpu_ms = sum(m.cpu_user_ms + m.cpu_system_ms for m in metrics)
        total_memory_mb = sum(m.memory_rss_mb for m in metrics)
        total_io_bytes = sum(m.io_read_bytes + m.io_write_bytes for m in metrics)
        total_io_ops = sum(m.io_read_count + m.io_write_count for m in metrics)
        total_threads = sum(m.num_threads for m in metrics)
        total_wakeups = sum(m.num_threads for m in metrics)  # Approximation

        # Avoid division by zero
        if total_cpu_ms == 0:
            total_cpu_ms = 1
        if total_memory_mb == 0:
            total_memory_mb = 1
        if total_io_bytes == 0:
            total_io_bytes = 1
        if total_io_ops == 0:
            total_io_ops = 1

        # Estimate system power if not provided (fallback to reasonable estimate)
        if self.system_power and self.system_power.total_system_power_mw > 0:
            system_power_mw = self.system_power.total_system_power_mw
        else:
            # Estimate based on typical idle power + activity
            # Typical macOS system: idle ~2W, active ~10W
            system_power_mw = 5000 + (total_cpu_ms / 100)  # Base + proportional to CPU time

        # Attribute power to each process
        estimated_metrics = []
        for metric in metrics:
            cpu_fraction = (metric.cpu_user_ms + metric.cpu_system_ms) / total_cpu_ms if total_cpu_ms > 0 else 0
            memory_fraction = metric.memory_rss_mb / total_memory_mb if total_memory_mb > 0 else 0
            io_fraction = (metric.io_read_bytes + metric.io_write_bytes) / total_io_bytes if total_io_bytes > 0 else 0
            wakeup_fraction = metric.num_threads / total_threads if total_threads > 0 else 0

            # Weighted power attribution
            app_power_mw = (
                system_power_mw * cpu_fraction * self.CPU_TIME_WEIGHT +
                system_power_mw * memory_fraction * self.MEMORY_WEIGHT +
                system_power_mw * io_fraction * self.IO_WEIGHT +
                system_power_mw * wakeup_fraction * self.WAKEUP_WEIGHT
            )

            # Convert power to energy: energy = power * time
            # Assuming typical laptop battery capacity
            app_energy_mah = self._power_to_mah(app_power_mw, interval_seconds)

            # Update metric with estimates
            metric.estimated_power_mw = app_power_mw
            metric.estimated_energy_mah = app_energy_mah

            estimated_metrics.append(metric)

        # Sort by energy descending
        estimated_metrics.sort(key=lambda m: m.estimated_energy_mah, reverse=True)

        return estimated_metrics

    @staticmethod
    def _power_to_mah(power_mw: float, interval_seconds: float,
                     voltage: float = 15.0) -> float:
        """Convert power to energy in milliamp-hours.

        Args:
            power_mw: Power in milliwatts
            interval_seconds: Time duration in seconds
            voltage: Battery voltage (typical MacBook battery: 15V)

        Returns:
            Energy in milliamp-hours
        """
        # Power (mW) = Voltage (V) × Current (mA)
        # So Current (mA) = Power / Voltage
        current_ma = power_mw / voltage

        # Energy (mAh) = Current (mA) × Time (hours)
        time_hours = interval_seconds / 3600
        energy_mah = current_ma * time_hours

        return energy_mah

    @staticmethod
    def get_top_energy_consumers(metrics: List[ProcessMetric],
                                 num_apps: int = 10) -> List[ProcessMetric]:
        """Get the top N energy-consuming apps.

        Args:
            metrics: List of ProcessMetric objects
            num_apps: Number of top apps to return

        Returns:
            List of top ProcessMetric objects sorted by energy (descending)
        """
        sorted_metrics = sorted(metrics,
                               key=lambda m: m.estimated_energy_mah,
                               reverse=True)
        return sorted_metrics[:num_apps]
