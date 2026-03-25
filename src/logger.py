"""Logger utility using Rich for formatted output."""

import sys
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.logging import RichHandler


class AppLogger:
    """Centralized logger with Rich formatting."""

    def __init__(self, name: str = "app-energy", log_file: Path = None):
        """Initialize logger with optional file output.

        Args:
            name: Logger name
            log_file: Path to log file (optional)
        """
        self.log_file = log_file

        # Create console for stderr
        self.console = Console(file=sys.stderr, force_terminal=True)

        # Create console for file if provided
        self.file_console = None
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handle = open(log_file, "a")
            self.file_console = Console(file=file_handle, force_terminal=False)

    def info(self, message: str):
        """Log info message."""
        self.console.print(f"[cyan]ℹ[/cyan] {message}")
        if self.file_console:
            self.file_console.print(f"[{datetime.now().isoformat()}] INFO: {message}")

    def success(self, message: str):
        """Log success message."""
        self.console.print(f"[green]✓[/green] {message}")
        if self.file_console:
            self.file_console.print(f"[{datetime.now().isoformat()}] SUCCESS: {message}")

    def warning(self, message: str):
        """Log warning message."""
        self.console.print(f"[yellow]⚠[/yellow] {message}")
        if self.file_console:
            self.file_console.print(f"[{datetime.now().isoformat()}] WARNING: {message}")

    def error(self, message: str):
        """Log error message."""
        self.console.print(f"[red]✗[/red] {message}")
        if self.file_console:
            self.file_console.print(f"[{datetime.now().isoformat()}] ERROR: {message}")

    def debug(self, message: str):
        """Log debug message."""
        self.console.print(f"[dim][{datetime.now().isoformat()}] DEBUG: {message}[/dim]")
        if self.file_console:
            self.file_console.print(f"[{datetime.now().isoformat()}] DEBUG: {message}")

    def print_table(self, table):
        """Print a Rich Table."""
        self.console.print(table)
        if self.file_console:
            self.file_console.print(table)

    def print(self, content):
        """Print content directly."""
        self.console.print(content)
        if self.file_console:
            self.file_console.print(content)


# Global logger instance
_logger = None

def get_logger(log_file: Path = None) -> AppLogger:
    """Get or create global logger instance."""
    global _logger
    if _logger is None:
        _logger = AppLogger(log_file=log_file)
    return _logger


def set_log_file(log_file: Path):
    """Update log file for global logger."""
    global _logger
    _logger = AppLogger(log_file=log_file)
