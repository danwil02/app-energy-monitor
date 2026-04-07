"""Live dashboard for real-time energy monitoring."""

from datetime import datetime, timedelta
from collections import deque
from typing import Optional, Dict, List
from pathlib import Path
import pandas as pd
import subprocess

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text

from .models import ProcessMetric, SystemPowerSample
from .logger import get_logger

logger = get_logger()


class LiveDashboard:
    """Real-time energy consumption dashboard with live updates."""

    def __init__(self, csv_path: Path, battery_wh: float, battery_mah: float, console: Console):
        """Initialize the live dashboard.

        Args:
            csv_path: Path to energy_log.csv
            battery_wh: Battery capacity in watt-hours
            battery_mah: Battery capacity in milliamp-hours
            console: Rich Console instance
        """
        self.csv_path = csv_path
        self.battery_wh = battery_wh
        self.battery_mah = battery_mah
        self.console = console

        # State
        self.current_table_index = 0  # 0=6h, 1=1d, 2=3d, 3=7d, 4=14d
        self.time_windows = {
            '6h': 6,
            '1d': 24,
            '3d': 72,
            '7d': 168,
            '14d': 336
        }
        self.window_names = list(self.time_windows.keys())

        # Latest data
        self.latest_metrics: Optional[List[ProcessMetric]] = None
        self.latest_power_sample: Optional[SystemPowerSample] = None
        self.sample_count = 0
        self.last_update_time = datetime.now()

        # Live logs buffer
        self.logs = deque(maxlen=50)

        # Battery info
        self.battery_percent: Optional[float] = None
        self.battery_time_remaining: Optional[str] = None
        self._update_battery_info()

    def add_log(self, message: str):
        """Add a log message to the dashboard."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {message}")

    def _update_battery_info(self):
        """Update battery percentage and time remaining from pmset."""
        try:
            result = subprocess.run(
                ['pmset', '-g', 'batt'],
                capture_output=True,
                text=True,
                timeout=2
            )

            # Parse output like:
            # -InternalBattery-0 (id=123); 62%; charging; 2:30 remaining
            for line in result.stdout.split('\n'):
                if '%' in line and 'Battery' not in line:
                    # Extract percentage
                    pct_idx = line.find('%')
                    if pct_idx > 0:
                        # Find the number before %
                        start = pct_idx - 1
                        while start >= 0 and (line[start].isdigit() or line[start] == '.'):
                            start -= 1
                        try:
                            self.battery_percent = float(line[start+1:pct_idx])
                        except ValueError:
                            pass

                    # Extract time remaining
                    if 'remaining' in line:
                        remaining_idx = line.find('remaining')
                        time_start = line.rfind(';', 0, remaining_idx)
                        if time_start >= 0:
                            self.battery_time_remaining = line[time_start+1:remaining_idx].strip()
        except Exception as e:
            logger.debug(f"Failed to get battery info: {e}")

    def _build_battery_indicator(self) -> str:
        """Build a battery progress indicator.

        Returns:
            Formatted battery bar string
        """
        self._update_battery_info()  # Refresh battery info

        if self.battery_percent is None:
            return "Battery: ?"

        # Create a simple bar: █ for filled, ░ for empty
        bar_width = 10
        filled = int(self.battery_percent / 100 * bar_width)
        empty = bar_width - filled
        bar = '█' * filled + '░' * empty

        time_str = f" ({self.battery_time_remaining})" if self.battery_time_remaining else ""
        return f"Battery: {bar} {self.battery_percent:.0f}%{time_str}"

    def update(self, metrics: List[ProcessMetric], power_sample: Optional[SystemPowerSample],
               sample_count: int):
        """Update dashboard with new collection data.

        Args:
            metrics: List of ProcessMetric objects from latest collection
            power_sample: Latest system power sample
            sample_count: Total number of samples collected so far
        """
        self.latest_metrics = metrics
        self.latest_power_sample = power_sample
        self.sample_count = sample_count
        self.last_update_time = datetime.now()

    def next_table(self):
        """Switch to next table window."""
        self.current_table_index = (self.current_table_index + 1) % len(self.window_names)

    def prev_table(self):
        """Switch to previous table window."""
        self.current_table_index = (self.current_table_index - 1) % len(self.window_names)

    def _get_window_dataframe(self, hours: int) -> pd.DataFrame:
        """Load and filter CSV data for time window.

        Args:
            hours: Number of hours to look back

        Returns:
            Filtered DataFrame with app energy aggregated
        """
        if not self.csv_path.exists():
            return pd.DataFrame()

        try:
            df = pd.read_csv(self.csv_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            cutoff_time = pd.Timestamp.now() - pd.Timedelta(hours=hours)
            df = df[df['timestamp'] >= cutoff_time]

            if df.empty:
                return df

            # Group by app_name and sum energy
            app_energy = df.groupby('app_name').agg({
                'estimated_energy_mah': 'sum',
                'estimated_power_mw': 'mean',
                'pid': 'count'  # Sample count
            }).rename(columns={'pid': 'samples'}).sort_values('estimated_energy_mah', ascending=False)

            return app_energy
        except Exception as e:
            logger.debug(f"Error reading CSV for dashboard: {e}")
            return pd.DataFrame()

    def _build_top_apps_panel(self, limit: int = 10) -> Panel:
        """Build panel showing top energy-consuming apps with visualizations.

        Args:
            limit: Number of top apps to show

        Returns:
            Rich Panel with formatted top apps
        """
        if not self.latest_metrics:
            return Panel("Waiting for data...", title="Top Energy Consumers")

        # Get current top apps
        app_power = {}
        for metric in self.latest_metrics:
            if metric.app_name not in app_power:
                app_power[metric.app_name] = 0.0
            app_power[metric.app_name] += metric.estimated_power_mw

        sorted_apps = sorted(app_power.items(), key=lambda x: x[1], reverse=True)[:limit]

        if not sorted_apps:
            return Panel("No app data", title="Top Energy Consumers")

        # Build text with prettier ASCII bars and color coding
        from rich.text import Text as RichText
        content = RichText()
        max_power = sorted_apps[0][1]

        for i, (app_name, power) in enumerate(sorted_apps):
            bar_width = int((power / max_power) * 35) if max_power > 0 else 0

            # Color code based on power level
            if power > max_power * 0.7:
                bar_char = "█"
                bar_color = "red"
            elif power > max_power * 0.4:
                bar_char = "█"
                bar_color = "yellow"
            else:
                bar_char = "▄"
                bar_color = "green"

            bar = bar_char * bar_width
            power_mw = f"{power:.1f}mW"
            line = f"{app_name[:20]:20s} {bar:35s} {power_mw:>8s}\n"
            content.append(line, style=bar_color if i == 0 else "")

        return Panel(content, title="Top Energy Consumers (Current Power)", expand=False)

    def _build_time_window_table(self, window_name: str) -> Table:
        """Build table for a specific time window.

        Args:
            window_name: One of '6h', '1d', '3d', '7d', '14d'

        Returns:
            Rich Table with energy data for that window
        """
        hours = self.time_windows[window_name]
        df = self._get_window_dataframe(hours)

        table = Table(title=f"Energy Report ({window_name})")
        table.add_column("App", style="cyan", width=30)
        table.add_column("Energy (mAh)", justify="right", style="red")
        table.add_column("Battery %", justify="right", style="green")
        table.add_column("Avg Power (mW)", justify="right", style="yellow")
        table.add_column("Samples", justify="right", style="magenta")

        if df.empty:
            table.add_row("No data", "", "", "", "")
            return table

        for app_name, row in df.head(15).iterrows():
            energy = row['estimated_energy_mah']
            battery_pct = (energy / self.battery_mah) * 100
            avg_power = row['estimated_power_mw']
            samples = int(row['samples'])

            table.add_row(
                str(app_name)[:30],
                f"{energy:.4f}",
                f"{battery_pct:.3f}%",
                f"{avg_power:.1f}",
                str(samples)
            )

        return table

    def _build_system_power_panel(self) -> Panel:
        """Build panel showing current system power."""
        if not self.latest_power_sample:
            return Panel("No power data", title="System Power")

        cpu_mw = self.latest_power_sample.cpu_power_mw
        gpu_mw = self.latest_power_sample.gpu_power_mw
        total_mw = self.latest_power_sample.total_system_power_mw

        content = (
            f"CPU Power:   {cpu_mw:>8.2f} mW  ({cpu_mw/1000:>6.3f}W)\n"
            f"GPU Power:   {gpu_mw:>8.2f} mW  ({gpu_mw/1000:>6.3f}W)\n"
            f"Total Power: {total_mw:>8.2f} mW  ({total_mw/1000:>6.3f}W)"
        )

        return Panel(content, title="System Power", expand=False)

    def _build_logs_panel(self) -> Panel:
        """Build panel with recent daemon logs."""
        log_text = "\n".join(self.logs) if self.logs else "No logs yet"
        return Panel(log_text, title="Activity Log", expand=False, height=8)

    def _build_status_line(self) -> Text:
        """Build status text showing current table and sample count."""
        window_indicator = f"[{self.current_table_index + 1}/{len(self.window_names)}] {self.window_names[self.current_table_index]}"
        sample_indicator = f"Sample: {self.sample_count}"
        timestamp = self.last_update_time.strftime("%H:%M:%S") if self.sample_count > 0 else "waiting..."
        battery_indicator = self._build_battery_indicator()

        status = f"{window_indicator}  |  {sample_indicator}  |  {battery_indicator}  |  Updated: {timestamp}"
        return Text(status, style="bold cyan")

    def _get_visible_windows(self) -> list:
        """Get list of visible time windows based on terminal size.

        Returns:
            List of window names to show
        """
        is_very_small = self.console.width < 100 or self.console.height < 25

        if is_very_small:
            # Show only 6h, 1d, 3d
            return ['6h', '1d', '3d']
        else:
            # Show all windows
            return self.window_names

    def render(self) -> Layout:
        """Render the complete dashboard layout.

        Returns:
            Rich Layout for the dashboard
        """
        # Detect terminal size
        width = self.console.width
        height = self.console.height

        # Choose layout based on terminal size
        is_small = width < 120 or height < 35
        is_very_small = width < 100 or height < 25

        # Get visible windows
        visible_windows = self._get_visible_windows()

        # Adjust current index if window is hidden
        if self.current_table_index >= len(visible_windows):
            self.current_table_index = 0

        if is_very_small:
            # Minimal mode: just status, top apps, and current table
            current_window = visible_windows[self.current_table_index]
            time_table = self._build_time_window_table(current_window)

            layout = Layout()
            layout.split_column(
                Layout(name="status", size=1),
                Layout(name="top_apps", size=8),
                Layout(name="table", size=None),
                Layout(name="logs", size=4)
            )

            layout["status"].update(self._build_status_line())
            layout["top_apps"].update(self._build_top_apps_panel(limit=5))
            layout["table"].update(time_table)
            layout["logs"].update(self._build_logs_panel())

        elif is_small:
            # Compact mode: single table, top apps, logs
            current_window = visible_windows[self.current_table_index]
            time_table = self._build_time_window_table(current_window)

            layout = Layout()
            layout.split_column(
                Layout(name="status", size=1),
                Layout(name="top_apps", size=10),
                Layout(name="power", size=4),
                Layout(name="table", size=None),
                Layout(name="logs", size=6)
            )

            layout["status"].update(self._build_status_line())
            layout["top_apps"].update(self._build_top_apps_panel(limit=8))
            layout["power"].update(self._build_system_power_panel())
            layout["table"].update(time_table)
            layout["logs"].update(self._build_logs_panel())
        else:
            # Full mode: show all visible tables side by side
            layout = Layout()
            layout.split_column(
                Layout(name="status", size=1),
                Layout(name="content", size=None),
                Layout(name="logs", size=8)
            )

            layout["status"].update(self._build_status_line())

            # Content area: top apps on left, current table on right
            content_layout = Layout()
            content_layout.split_row(
                Layout(name="top_apps", size=50),
                Layout(name="tables", size=None)
            )

            current_window = visible_windows[self.current_table_index]
            time_table = self._build_time_window_table(current_window)

            content_layout["top_apps"].update(self._build_top_apps_panel(limit=10))
            content_layout["tables"].split_column(
                Layout(self._build_system_power_panel(), name="power", size=5),
                Layout(time_table, name="table")
            )

            layout["content"].update(content_layout)
            layout["logs"].update(self._build_logs_panel())

        return layout
