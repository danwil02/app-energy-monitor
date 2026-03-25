"""Tests for the energy monitor."""

import pytest
from pathlib import Path
from datetime import datetime
from src.models import ProcessMetric, SystemPowerSample
from src.energy_estimator import EnergyEstimator
from src.csv_writer import CSVWriter


@pytest.fixture
def temp_csv_path(tmp_path):
    """Fixture for temporary CSV path."""
    return tmp_path / "test_energy.csv"


@pytest.fixture
def sample_metrics():
    """Fixture for sample process metrics."""
    timestamp = datetime.now()
    return [
        ProcessMetric(
            timestamp=timestamp,
            pid=100,
            app_name="TestApp1",
            cpu_user_ms=5000,
            cpu_system_ms=2000,
            memory_rss_mb=512,
            memory_vms_mb=1024,
            io_read_count=100,
            io_write_count=50,
            io_read_bytes=1024 * 1024,  # 1 MB
            io_write_bytes=512 * 1024,  # 512 KB
            num_threads=4,
            num_fds=10,
        ),
        ProcessMetric(
            timestamp=timestamp,
            pid=101,
            app_name="TestApp2",
            cpu_user_ms=2000,
            cpu_system_ms=1000,
            memory_rss_mb=256,
            memory_vms_mb=512,
            io_read_count=50,
            io_write_count=25,
            io_read_bytes=512 * 1024,
            io_write_bytes=256 * 1024,
            num_threads=2,
            num_fds=5,
        ),
    ]


@pytest.fixture
def sample_power():
    """Fixture for sample system power."""
    return SystemPowerSample(
        timestamp=datetime.now(),
        total_system_power_mw=10000,
        cpu_power_mw=6000,
        gpu_power_mw=3000,
        system_memory_power_mw=1000,
        total_package_idle_exits=100,
        total_platform_timer_wakeups=500,
    )


class TestEnergyEstimator:
    """Test energy estimator."""

    def test_estimate_energy_calculates_values(self, sample_metrics, sample_power):
        """Test that energy estimation produces non-zero values."""
        estimator = EnergyEstimator(system_power_sample=sample_power)
        result = estimator.estimate_energy(sample_metrics, interval_seconds=60)

        assert len(result) == len(sample_metrics)
        assert all(m.estimated_power_mw > 0 for m in result)
        assert all(m.estimated_energy_mah > 0 for m in result)

    def test_estimate_energy_maintains_order(self, sample_metrics):
        """Test that results are sorted by energy."""
        estimator = EnergyEstimator()
        result = estimator.estimate_energy(sample_metrics)

        # Check sorted in descending order
        for i in range(len(result) - 1):
            assert result[i].estimated_energy_mah >= result[i + 1].estimated_energy_mah

    def test_get_top_consumers(self, sample_metrics):
        """Test top energy consumers filtering."""
        result = EnergyEstimator.get_top_energy_consumers(sample_metrics, num_apps=1)
        assert len(result) <= 1

    def test_power_to_mah_conversion(self):
        """Test power to energy conversion."""
        # 1 W (1000 mW) for 1 hour at 15V = 1000/15 = 66.67 mAh
        energy = EnergyEstimator._power_to_mah(power_mw=1000, interval_seconds=3600, voltage=15)
        assert 66 < energy < 67


class TestCSVWriter:
    """Test CSV writer."""

    def test_csv_writer_creates_file(self, temp_csv_path, sample_metrics):
        """Test that CSV file is created."""
        writer = CSVWriter(csv_path=temp_csv_path)
        count = writer.write_metrics(sample_metrics)

        assert temp_csv_path.exists()
        assert count == len(sample_metrics)

    def test_csv_writer_includes_headers(self, temp_csv_path):
        """Test that CSV includes headers."""
        writer = CSVWriter(csv_path=temp_csv_path)

        with open(temp_csv_path) as f:
            first_line = f.readline().strip()

        assert 'timestamp' in first_line
        assert 'app_name' in first_line
        assert 'estimated_energy_mah' in first_line

    def test_csv_writer_appends_data(self, temp_csv_path, sample_metrics):
        """Test that CSV writer appends data."""
        writer = CSVWriter(csv_path=temp_csv_path)

        # Write once
        writer.write_metrics(sample_metrics[:1])
        first_count = writer.get_row_count()

        # Write again
        writer.write_metrics(sample_metrics[1:])
        second_count = writer.get_row_count()

        assert second_count == first_count + 1


class TestProcessMetric:
    """Test process metric model."""

    def test_metric_to_dict(self):
        """Test converting metric to dictionary."""
        metric = ProcessMetric(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            pid=100,
            app_name="TestApp",
            cpu_user_ms=1000,
            cpu_system_ms=500,
            memory_rss_mb=512,
            memory_vms_mb=1024,
            io_read_count=10,
            io_write_count=5,
            io_read_bytes=1024,
            io_write_bytes=512,
            num_threads=2,
            num_fds=5,
            estimated_energy_mah=0.1,
            estimated_power_mw=100,
        )

        result = metric.to_dict()

        assert isinstance(result, dict)
        assert result['pid'] == 100
        assert result['app_name'] == "TestApp"
        assert 'timestamp' in result
