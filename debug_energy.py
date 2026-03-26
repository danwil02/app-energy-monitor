#!/usr/bin/env python3
"""Debug energy data statistics."""

import pandas as pd
from datetime import timedelta

# Load data
df = pd.read_csv('data/energy_log.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Last 10 hours
cutoff = df['timestamp'].max() - timedelta(hours=10)
df_recent = df[df['timestamp'] >= cutoff].copy()

print(f"Total rows: {len(df_recent)}")
print(f"Estimated power stats (mW):")
print(f"  Min: {df_recent['estimated_power_mw'].min():.2f}")
print(f"  Max: {df_recent['estimated_power_mw'].max():.2f}")
print(f"  Mean: {df_recent['estimated_power_mw'].mean():.2f}")
print(f"  Sum: {df_recent['estimated_power_mw'].sum():.2f}")
print()
print(f"Estimated energy stats (mAh):")
print(f"  Min: {df_recent['estimated_energy_mah'].min():.2f}")
print(f"  Max: {df_recent['estimated_energy_mah'].max():.2f}")
print(f"  Mean: {df_recent['estimated_energy_mah'].mean():.2f}")
print(f"  Sum: {df_recent['estimated_energy_mah'].sum():.2f}")
print()

# Calculate what the battery should be
total_mah = df_recent['estimated_energy_mah'].sum()
actual_drain_pct = 0.13  # 80% to 67%
required_capacity = total_mah / actual_drain_pct
required_wh = required_capacity * 15 / 1000

print(f"Reverse calculation:")
print(f"  Total estimated energy: {total_mah:.2f}mAh")
print(f"  Actual drain: {actual_drain_pct*100:.1f}%")
print(f"  Required battery capacity: {required_capacity:.0f}mAh ({required_wh:.1f}Wh)")
print()

# Time calculation
duration_hours = (df_recent['timestamp'].max() - df_recent['timestamp'].min()).total_seconds() / 3600
avg_power_w = df_recent['estimated_power_mw'].mean() / 1000
expected_energy_wh = avg_power_w * duration_hours
expected_energy_mah = expected_energy_wh * 1000 / 15

print(f"Time-based calculation:")
print(f"  Duration: {duration_hours:.2f} hours")
print(f"  Avg power draw: {avg_power_w:.3f}W")
print(f"  Expected energy: {expected_energy_wh:.2f}Wh ({expected_energy_mah:.0f}mAh)")
print()

print("Sample rows:")
print(df_recent[['timestamp', 'app_name', 'estimated_power_mw', 'estimated_energy_mah']].head(20).to_string())
