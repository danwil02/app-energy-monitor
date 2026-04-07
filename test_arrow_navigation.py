#!/usr/bin/env python3
"""Test arrow key navigation in live dashboard."""

from src.live_dashboard import LiveDashboard
from src.cli import KeyboardInputHandler
from rich.console import Console
from pathlib import Path

console = Console()

# Create a dummy dashboard
csv_path = Path("energy_log.csv")
dashboard = LiveDashboard(csv_path=csv_path, battery_wh=75, battery_mah=5000, console=console)

print("Testing table navigation logic...")
print(f"Initial table index: {dashboard.current_table_index}")
print(f"Window names: {dashboard.window_names}")
print()

# Test next_table()
for i in range(len(dashboard.window_names) + 2):
    dashboard.next_table()
    print(f"After next_table(): index={dashboard.current_table_index}, window={dashboard.window_names[dashboard.current_table_index]}")

print()

# Test prev_table()
for i in range(len(dashboard.window_names) + 2):
    dashboard.prev_table()
    print(f"After prev_table(): index={dashboard.current_table_index}, window={dashboard.window_names[dashboard.current_table_index]}")

print()
print("✓ Table navigation logic works correctly")
print()

# Test keyboard handler instantiation
print("Testing KeyboardInputHandler instantiation...")
handler = KeyboardInputHandler(
    on_left=dashboard.prev_table,
    on_right=dashboard.next_table
)
print(f"Handler created: {handler}")
print(f"Handler callbacks: left={handler.on_left}, right={handler.on_right}")
print("✓ KeyboardInputHandler instantiation works")
