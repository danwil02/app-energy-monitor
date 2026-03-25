"""Parser for macOS powermetrics command output."""

import subprocess
from datetime import datetime
from typing import Optional
from .models import SystemPowerSample
from .logger import get_logger

logger = get_logger()


class PowermetricsParser:
    """Parse output from macOS 'powermetrics' command.

    Note: powermetrics requires superuser privileges. Run commands with sudo:
        sudo poetry run app-energy collect
        sudo poetry run app-energy daemon

    Or configure passwordless sudo for powermetrics:
        sudo visudo
        # Add this line:
        # %admin ALL=(ALL) NOPASSWD: /usr/bin/powermetrics
    """

    @staticmethod
    def get_system_power() -> Optional[SystemPowerSample]:
        """Get current system power metrics using powermetrics command.

        Returns:
            SystemPowerSample with current power metrics, or None if failed
        """
        try:
            cmd = ['powermetrics', '-i', '1000', '-n', '1', '--samplers',
                   'cpu_power,gpu_power,disk', '-f', 'plist']

            # Try with sudo first (most common case on macOS)
            result = None
            try:
                result = subprocess.run(
                    ['sudo', '-n'] + cmd,  # -n: non-interactive sudo
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            except subprocess.TimeoutExpired:
                pass

            # If sudo non-interactive fails, try without sudo
            if not result or result.returncode != 0:
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    return PowermetricsParser._create_dummy_sample()

            if result.returncode != 0:
                # Log helpful message about sudo requirement
                error_msg = result.stderr.lower()
                if "superuser" in error_msg or "permission" in error_msg:
                    logger.debug("powermetrics requires sudo. Run: sudo poetry run app-energy collect")
                else:
                    logger.debug(f"powermetrics error: {result.stderr}")
                return PowermetricsParser._create_dummy_sample()

            # Parse plist output
            return PowermetricsParser._parse_plist_output(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.debug(f"Failed to run powermetrics: {e}")
            return PowermetricsParser._create_dummy_sample()

    @staticmethod
    def _create_dummy_sample() -> SystemPowerSample:
        """Create a dummy sample when powermetrics is unavailable.

        This allows the collector to work even when powermetrics isn't available.
        """
        return SystemPowerSample(
            timestamp=datetime.now(),
            total_system_power_mw=0.0,
            cpu_power_mw=0.0,
            gpu_power_mw=0.0,
            system_memory_power_mw=0.0,
            total_package_idle_exits=0,
            total_platform_timer_wakeups=0,
        )

    @staticmethod
    def _parse_plist_output(plist_text: str) -> SystemPowerSample:
        """Parse plist format output from powermetrics.

        Tries multiple parsing strategies to extract power values.
        Keys to look for: cpu_power, gpu_power, combined_power (in watts).

        Args:
            plist_text: Raw plist output from powermetrics command

        Returns:
            SystemPowerSample object
        """
        timestamp = datetime.now()
        cpu_power_mw = 0.0
        gpu_power_mw = 0.0

        try:
            import plistlib
            # Try native plistlib parsing first
            try:
                plist_start = plist_text.find('<?xml')
                if plist_start != -1:
                    plist_data = plist_text[plist_start:].encode()
                    plist_dict = plistlib.loads(plist_data)

                    if isinstance(plist_dict, dict):
                        # Direct key lookup for cpu_power and gpu_power (case-insensitive)
                        for key in plist_dict:
                            key_lower = key.lower() if isinstance(key, str) else ""
                            if key_lower == 'cpu_power':
                                val = plist_dict[key]
                                if isinstance(val, (int, float)):
                                    cpu_power_mw = float(val) * 1000
                            elif key_lower == 'gpu_power':
                                val = plist_dict[key]
                                if isinstance(val, (int, float)):
                                    gpu_power_mw = float(val) * 1000
            except Exception as e:
                logger.debug(f"plistlib parsing failed: {e}, trying regex parsing")
        except ImportError:
            logger.debug("plistlib not available, using regex parsing")

        # Fallback: regex-based XML parsing for patterns
        # This catches cases like: <key>cpu_power</key><real>1188.52</real>
        if cpu_power_mw == 0.0 or gpu_power_mw == 0.0:
            try:
                import re
                # Look for cpu_power key with real value
                cpu_match = re.search(r'<key>cpu_power</key>\s*<real>([\d.]+)</real>', plist_text, re.IGNORECASE)
                if cpu_match:
                    cpu_power_mw = float(cpu_match.group(1)) * 1000

                # Look for gpu_power key with real value
                gpu_match = re.search(r'<key>gpu_power</key>\s*<real>([\d.]+)</real>', plist_text, re.IGNORECASE)
                if gpu_match:
                    gpu_power_mw = float(gpu_match.group(1)) * 1000

                # Fallback: if individual values not found, try combined_power
                if cpu_power_mw == 0.0 and gpu_power_mw == 0.0:
                    combined_match = re.search(r'<key>combined_power</key>\s*<real>([\d.]+)</real>', plist_text, re.IGNORECASE)
                    if combined_match:
                        cpu_power_mw = float(combined_match.group(1)) * 1000
            except Exception as e:
                logger.debug(f"Regex parsing failed: {e}")

        return SystemPowerSample(
            timestamp=timestamp,
            total_system_power_mw=cpu_power_mw + gpu_power_mw,
            cpu_power_mw=cpu_power_mw,
            gpu_power_mw=gpu_power_mw,
            system_memory_power_mw=0.0,
            total_package_idle_exits=0,
            total_platform_timer_wakeups=0,
        )
