"""Click CLI application for energy monitor."""

import click
import time
import signal
import sys
import subprocess
import threading
import select
from pathlib import Path
from datetime import datetime
from rich.table import Table
from rich.console import Console
from rich.syntax import Syntax
from rich.live import Live
from typing import Optional, Callable

from .config import (
    INFLUXDB_URL, INFLUXDB_ORG, INFLUXDB_BUCKET, INFLUXDB_TOKEN,
    COLLECTION_INTERVAL, CSV_PATH, LOG_PATH, APP_WHITELIST, APP_BLACKLIST
)
from .collector import MetricsCollector
from .energy_estimator import EnergyEstimator
from .powermetrics_parser import PowermetricsParser
from .csv_writer import CSVWriter
from .storage import InfluxDBWriter
from .logger import get_logger, set_log_file
from .live_dashboard import LiveDashboard

console = Console()


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f}TB"


class KeyboardInputHandler:
    """Handle keyboard input in terminal without blocking main loop.

    Uses select() to check for input availability without changing terminal modes,
    avoiding conflicts with Rich's Live display terminal management.
    """

    def __init__(self, on_left: Callable = None, on_right: Callable = None):
        """Initialize keyboard handler.

        Args:
            on_left: Callback for left arrow key
            on_right: Callback for right arrow key
        """
        self.on_left = on_left
        self.on_right = on_right
        self.thread = None
        self.running = False
        self.logger = get_logger()

    def start(self):
        """Start keyboard input handler in background thread."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._input_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop keyboard input handler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)

    def _input_loop(self):
        """Main input handling loop (runs in thread).

        Uses select() to check if input is available without changing terminal modes.
        This is safer and doesn't interfere with Rich's Live display.
        """
        try:
            while self.running:
                try:
                    # Use select to check if input is available (non-blocking)
                    # Timeout of 0.5 seconds allows for frequent checks while avoiding busy-waiting
                    ready = select.select([sys.stdin], [], [], 0.5)

                    if ready[0]:
                        # Try to read the next character
                        ch = sys.stdin.read(1)

                        if not ch:  # EOF
                            continue

                        if ch == '\x1b':  # Escape character (start of escape sequence)
                            # Try to read the rest of the escape sequence
                            # Arrow keys are: ESC [ A (up), ESC [ B (down), ESC [ C (right), ESC [ D (left)
                            ch2_ready = select.select([sys.stdin], [], [], 0.05)
                            if ch2_ready[0]:
                                ch2 = sys.stdin.read(1)
                                if ch2 == '[':
                                    ch3_ready = select.select([sys.stdin], [], [], 0.05)
                                    if ch3_ready[0]:
                                        ch3 = sys.stdin.read(1)
                                        if ch3 == 'C' and self.on_right:
                                            # Right arrow detected
                                            self.logger.debug("Right arrow key detected")
                                            self.on_right()
                                        elif ch3 == 'D' and self.on_left:
                                            # Left arrow detected
                                            self.logger.debug("Left arrow key detected")
                                            self.on_left()
                except EOFError:
                    # stdin was closed
                    self.logger.debug("stdin closed, stopping keyboard handler")
                    break
                except Exception as e:
                    # Silently ignore read errors and continue
                    self.logger.debug(f"Keyboard handler read error: {e}")
                    pass
        except Exception as e:
            # Silently fail - input handler errors shouldn't break the daemon
            self.logger.debug(f"Keyboard handler error: {e}")


@click.group()
def main():
    """App Energy Monitor - Track per-app energy consumption on macOS."""
    pass


@main.command()
@click.option('--interval', '-i', default=COLLECTION_INTERVAL,
              help='Sampling interval in seconds', type=int)
@click.option('--duration', '-d', default=None,
              help='Run for N minutes (None = forever)', type=int)
@click.option('--output', '-o', default='both',
              type=click.Choice(['csv', 'influxdb', 'both']),
              help='Output destination')
@click.option('--log-file', default=LOG_PATH,
              help='Path to daemon log file')
@click.option('--live', is_flag=True,
              help='Show real-time live dashboard')
def daemon(interval: int, duration: Optional[int], output: str, log_file: Path, live: bool):
    """Run as background daemon, continuously monitoring energy usage.

    For accurate power measurements, run with sudo:
        sudo poetry run app-energy daemon --interval 60 --output both

    For live dashboard:
        sudo poetry run app-energy daemon --live --interval 60
    """

    set_log_file(Path(log_file))
    logger = get_logger()

    logger.info(f"Starting energy monitor daemon (interval: {interval}s)")
    logger.info(f"Output: {output}")
    if live:
        logger.info("Live dashboard enabled")

    # Initialize collectors and writers
    collector = MetricsCollector(
        app_whitelist=APP_WHITELIST,
        app_blacklist=APP_BLACKLIST
    )
    estimator = EnergyEstimator()
    logger.info(f"Hardware model: {estimator.hw_model}")
    logger.info(f"Battery capacity: {estimator.battery_wh}Wh ({estimator.battery_mah:.0f}mAh)")

    csv_writer = None
    influxdb_writer = None
    dashboard = None
    keyboard_handler = None
    live_context = None

    if output in ['csv', 'both']:
        csv_writer = CSVWriter(csv_path=CSV_PATH)
        logger.info(f"CSV output: {CSV_PATH}")

    if output in ['influxdb', 'both']:
        if INFLUXDB_TOKEN:
            influxdb_writer = InfluxDBWriter(
                url=INFLUXDB_URL,
                org=INFLUXDB_ORG,
                bucket=INFLUXDB_BUCKET,
                token=INFLUXDB_TOKEN
            )
        else:
            logger.warning("InfluxDB token not configured, skipping InfluxDB output")

    if live:
        dashboard = LiveDashboard(
            csv_path=CSV_PATH,
            battery_wh=estimator.battery_wh,
            battery_mah=estimator.battery_mah,
            console=console
        )
        logger.info("Use ← / → arrow keys to switch time windows")

    def signal_handler(sig, frame):
        logger.info("Received interrupt signal, shutting down...")
        # Signal handler will exit - let finally block handle cleanup
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    start_time = time.time()
    sample_count = 0

    # Setup live display context if needed
    # NOTE: Keyboard input currently disabled due to conflicts with Rich's terminal control
    #       when both try to manage stdin. This will be improved in a future update.
    keyboard_handler = None
    live_context = None
    if dashboard:
        # keyboard_handler = KeyboardInputHandler(
        #     on_left=dashboard.prev_table,
        #     on_right=dashboard.next_table
        # )
        # keyboard_handler.start()
        # logger.info("Keyboard input handler started")

        live_context = Live(dashboard.render(), console=console, refresh_per_second=1)
        live_context.__enter__()

    try:
        while True:
            sample_time = datetime.now()

            # Collect metrics (use spinners only if not in live mode)
            if not dashboard:
                with console.status("[cyan]Collecting metrics...", spinner="dots"):
                    metrics = collector.collect_all()
            else:
                logger.info("Collecting metrics...")
                metrics = collector.collect_all()

            # Get system power
            if not dashboard:
                with console.status("[cyan]Getting power metrics...", spinner="dots"):
                    power_sample = PowermetricsParser.get_system_power()
            else:
                logger.info("Getting power metrics...")
                power_sample = PowermetricsParser.get_system_power()

            # Estimate energy
            if not dashboard:
                with console.status("[cyan]Estimating energy...", spinner="dots"):
                    estimator_instance = EnergyEstimator(system_power_sample=power_sample)
                    estimated_metrics = estimator_instance.estimate_energy(metrics, interval)
            else:
                logger.info("Estimating energy...")
                estimator_instance = EnergyEstimator(system_power_sample=power_sample)
                estimated_metrics = estimator_instance.estimate_energy(metrics, interval)

            # Write to CSV
            if csv_writer:
                csv_writer.write_metrics(estimated_metrics)
                if power_sample:
                    csv_writer.write_system_power(power_sample)

            # Write to InfluxDB
            if influxdb_writer:
                influxdb_writer.write_metrics(estimated_metrics)
                if power_sample:
                    influxdb_writer.write_system_power(power_sample)

            sample_count += 1

            # Log summary
            logger.info(f"Sample #{sample_count}: collected {len(metrics)} apps")

            # Update dashboard if enabled
            if dashboard:
                dashboard.update(estimated_metrics, power_sample, sample_count)
                dashboard.add_log(f"Sample #{sample_count}: {len(metrics)} apps")
                live_context.update(dashboard.render())

            # Calculate elapsed time
            elapsed = time.time() - start_time
            if duration and elapsed >= duration * 60:
                logger.info(f"Duration reached ({duration} minutes), shutting down...")
                break

            # Sleep until next interval
            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Daemon error: {e}")
    finally:
        try:
            if keyboard_handler:
                keyboard_handler.stop()
        except Exception as e:
            logger.debug(f"Error stopping keyboard handler: {e}")

        try:
            if live_context:
                live_context.__exit__(None, None, None)
        except Exception as e:
            logger.debug(f"Error exiting live context: {e}")

        try:
            if influxdb_writer:
                influxdb_writer.close()
        except Exception as e:
            logger.debug(f"Error closing InfluxDB writer: {e}")

        logger.info("Daemon stopped")


@main.command()
@click.option('--output', '-o', default='both',
              type=click.Choice(['csv', 'influxdb', 'both', 'table']),
              help='Output format')
@click.option('--top', '-t', default=10, type=int,
              help='Show top N apps')
def collect(output: str, top: int):
    """Perform a single collection and display/save results.

    For accurate power measurements, run with sudo:
        sudo poetry run app-energy collect
    """

    logger = get_logger()

    with console.status("[cyan]Collecting metrics...", spinner="dots"):
        collector = MetricsCollector(
            app_whitelist=APP_WHITELIST,
            app_blacklist=APP_BLACKLIST
        )
        metrics = collector.collect_all()

    with console.status("[cyan]Getting system power...", spinner="dots"):
        power_sample = PowermetricsParser.get_system_power()

    with console.status("[cyan]Estimating energy...", spinner="dots"):
        estimator = EnergyEstimator(system_power_sample=power_sample)
        logger.debug(f"Hardware model: {estimator.hw_model}")
        logger.debug(f"Battery capacity: {estimator.battery_wh}Wh ({estimator.battery_mah:.0f}mAh)")
        estimated_metrics = estimator.estimate_energy(metrics, interval_seconds=60)

    # Get top consumers
    top_metrics = EnergyEstimator.get_top_energy_consumers(estimated_metrics, top)

    # Output based on selection
    if output in ['table', 'both']:
        # Display table
        table = Table(title=f"Top {top} Energy Consumers")
        table.add_column("App", style="cyan")
        table.add_column("PID", justify="right", style="magenta")
        table.add_column("CPU (ms)", justify="right")
        table.add_column("Memory (MB)", justify="right", style="green")
        table.add_column("I/O (MB)", justify="right")
        table.add_column("Power (mW)", justify="right", style="yellow")
        table.add_column("Energy (mAh)", justify="right", style="red")

        for metric in top_metrics:
            io_mb = (metric.io_read_bytes + metric.io_write_bytes) / (1024 * 1024)
            table.add_row(
                metric.app_name[:30],
                str(metric.pid),
                f"{metric.cpu_user_ms + metric.cpu_system_ms:.0f}",
                f"{metric.memory_rss_mb:.1f}",
                f"{io_mb:.1f}",
                f"{metric.estimated_power_mw:.1f}",
                f"{metric.estimated_energy_mah:.4f}"
            )

        console.print(table)

    if output in ['csv', 'both']:
        csv_writer = CSVWriter(csv_path=CSV_PATH)
        csv_writer.write_metrics(estimated_metrics)
        if power_sample:
            csv_writer.write_system_power(power_sample)
        console.print(f"[green]✓[/green] Wrote {len(estimated_metrics)} metrics to {CSV_PATH}")

    if output in ['influxdb', 'both']:
        if INFLUXDB_TOKEN:
            influxdb_writer = InfluxDBWriter(
                url=INFLUXDB_URL,
                org=INFLUXDB_ORG,
                bucket=INFLUXDB_BUCKET,
                token=INFLUXDB_TOKEN
            )
            influxdb_writer.write_metrics(estimated_metrics)
            if power_sample:
                influxdb_writer.write_system_power(power_sample)
            influxdb_writer.close()
            console.print(f"[green]✓[/green] Wrote {len(estimated_metrics)} metrics to InfluxDB")
        else:
            console.print("[yellow]⚠[/yellow] InfluxDB token not configured")


@main.command()
@click.option('--hours', '-h', default=1, type=float,
              help='Show data from last N hours')
@click.option('--top', '-t', default=10, type=int,
              help='Show top N apps')
def report(hours: float, top: int):
    """Show energy consumption report from CSV data."""

    if not CSV_PATH.exists():
        console.print(f"[red]✗[/red] No data file found at {CSV_PATH}")
        return

    import pandas as pd

    try:
        # Get battery capacity for percentage calculation
        estimator = EnergyEstimator()
        battery_mah = estimator.battery_mah

        # Read CSV
        df = pd.read_csv(CSV_PATH)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Filter by time
        cutoff_time = pd.Timestamp.now() - pd.Timedelta(hours=hours)
        df = df[df['timestamp'] >= cutoff_time]

        if df.empty:
            console.print(f"[yellow]⚠[/yellow] No data found in last {hours} hour(s)")
            return

        # Group by app and sum energy
        app_energy = df.groupby('app_name')['estimated_energy_mah'].sum().sort_values(ascending=False)

        # Display table
        table = Table(title=f"Energy Report (Last {hours} hour(s)) - Battery: {estimator.battery_wh}Wh")
        table.add_column("App", style="cyan")
        table.add_column("Energy (mAh)", justify="right", style="red")
        table.add_column("Battery %", justify="right", style="green")
        table.add_column("Avg Power (mW)", justify="right", style="yellow")
        table.add_column("Samples", justify="right", style="magenta")

        for i, (app_name, energy) in enumerate(app_energy.head(top).items()):
            app_samples = df[df['app_name'] == app_name]
            avg_power = app_samples['estimated_power_mw'].mean()
            num_samples = len(app_samples)
            battery_pct = (energy / battery_mah) * 100

            table.add_row(
                app_name[:30],
                f"{energy:.4f}",
                f"{battery_pct:.3f}%",
                f"{avg_power:.1f}",
                str(num_samples)
            )

        console.print(table)

        # Summary stats
        total_energy = app_energy.sum()
        total_battery_pct = (total_energy / battery_mah) * 100
        console.print(f"\n[dim]Total energy: {total_energy:.4f} mAh ({total_battery_pct:.2f}% of battery)[/dim]")
        console.print(f"[dim]Data points: {len(df)}[/dim]")

    except ImportError:
        console.print("[red]✗[/red] pandas required for report command")
    except Exception as e:
        console.print(f"[red]✗[/red] Error generating report: {e}")


@main.command()
def status():
    """Show current monitoring status and statistics."""

    csv_writer = CSVWriter(csv_path=CSV_PATH)
    row_count = csv_writer.get_row_count()
    file_size = csv_writer.get_file_size_mb()

    table = Table(title="Monitoring Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("CSV Path", str(CSV_PATH))
    table.add_row("CSV Rows", str(row_count))
    table.add_row("CSV Size", f"{file_size:.2f} MB")
    table.add_row("Log Path", str(LOG_PATH))
    table.add_row("Collection Interval", f"{COLLECTION_INTERVAL}s")
    table.add_row("InfluxDB URL", INFLUXDB_URL if INFLUXDB_TOKEN else "Not configured")

    console.print(table)


@main.command()
@click.option('--show-raw', '-r', is_flag=True, help='Show raw powermetrics output')
def check_power(show_raw: bool):
    """Diagnostic command to test powermetrics and check power measurements.

    This helps debug why power values might be zero. Try with sudo for full access:
        sudo poetry run app-energy check-power --show-raw
    """
    console.print("\n[cyan]Checking powermetrics availability and functionality...[/cyan]\n")

    # Check if powermetrics executable exists
    result = subprocess.run(['which', 'powermetrics'], capture_output=True, text=True)
    if result.returncode == 0:
        console.print("[green]✓[/green] powermetrics executable found at:", result.stdout.strip())
    else:
        console.print("[red]✗[/red] powermetrics not found in PATH")
        return

    # Try to run powermetrics
    console.print("\n[cyan]Attempting to run powermetrics...[/cyan]\n")

    cmd = ['powermetrics', '-i', '1000', '-n', '1', '--samplers',
           'cpu_power,gpu_power,disk', '-f', 'plist']

    raw_output = None
    ran_with_sudo = False

    # Try with sudo first
    try:
        result = subprocess.run(
            ['sudo', '-n'] + cmd,
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0:
            console.print("[green]✓[/green] Ran successfully with [bold]sudo -n[/bold] (no password prompt)")
            raw_output = result.stdout
            ran_with_sudo = True
        elif "sudo" in result.stderr.lower() or "superuser" in result.stderr.lower():
            console.print("[yellow]⚠[/yellow] sudo without password not configured")
            console.print("   Trying without sudo...")
    except subprocess.TimeoutExpired:
        console.print("[yellow]⚠[/yellow] Command timed out with sudo -n")
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Error with sudo: {e}")

    # Try without sudo if sudo failed
    if not raw_output:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0:
                console.print("[green]✓[/green] Ran successfully [bold]without sudo[/bold]")
                raw_output = result.stdout
            else:
                error_msg = result.stderr
                if "superuser" in error_msg.lower() or "permission" in error_msg.lower():
                    console.print("[red]✗[/red] [bold]Permission denied[/bold] - powermetrics requires sudo")
                    console.print("\n[cyan]To fix, either:[/cyan]")
                    console.print("  1. Run with sudo: sudo poetry run app-energy check-power")
                    console.print("  2. Configure passwordless sudo:")
                    console.print("     sudo visudo")
                    console.print("     # Add: %admin ALL=(ALL) NOPASSWD: /usr/bin/powermetrics")
                else:
                    console.print(f"[red]✗[/red] Command failed: {error_msg}")
                return
        except subprocess.TimeoutExpired:
            console.print("[red]✗[/red] Command timed out")
            return
        except FileNotFoundError:
            console.print("[red]✗[/red] powermetrics not found")
            return

    # Show raw output if requested
    if show_raw and raw_output:
        console.print("\n[cyan]Raw powermetrics output (first 1000 chars):[/cyan]\n")
        output_display = raw_output[:1000] if len(raw_output) > 1000 else raw_output
        syntax = Syntax(output_display, "xml", theme="monokai", line_numbers=False)
        console.print(syntax)

    # Parse the output
    console.print("\n[cyan]Parsing power metrics...[/cyan]\n")
    power_sample = PowermetricsParser._parse_plist_output(raw_output)

    # Display results
    table = Table(title="Power Metrics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Status", style="magenta")

    cpu_status = "[green]✓[/green]" if power_sample.cpu_power_mw > 0 else "[yellow]⚠[/yellow]"
    gpu_status = "[green]✓[/green]" if power_sample.gpu_power_mw > 0 else "[yellow]ℹ[/yellow]"
    total_status = "[green]✓[/green]" if power_sample.total_system_power_mw > 0 else "[red]✗[/red]"

    table.add_row("CPU Power", f"{power_sample.cpu_power_mw:.2f} mW", cpu_status)
    table.add_row("GPU Power", f"{power_sample.gpu_power_mw:.2f} mW", gpu_status)
    table.add_row("Total Power", f"{power_sample.total_system_power_mw:.2f} mW", total_status)
    table.add_row("Timestamp", power_sample.timestamp.isoformat(), "[green]✓[/green]")

    console.print(table)

    # Diagnostic summary
    console.print("\n[cyan]Diagnostics:[/cyan]\n")
    if power_sample.total_system_power_mw == 0:
        console.print("[red]✗ Power values are all zero[/red]")
        console.print("   This usually means:")
        console.print("   - powermetrics output format changed")
        console.print("   - Power data not available on this system")
        console.print("   - Parsing logic doesn't match output format")
        if show_raw:
            console.print(f"\n[yellow]Raw output shown above - check if it contains power values[/yellow]")
        else:
            console.print(f"\n[yellow]Tip: Use --show-raw to see raw output for debugging[/yellow]")
    else:
        console.print(f"[green]✓ Power metrics working correctly![/green]")
        console.print(f"  Total system power: {power_sample.total_system_power_mw:.2f} mW")


if __name__ == '__main__':
    main()
