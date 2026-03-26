#!/usr/bin/env python3
"""Validate energy consumption data against actual battery drain."""

import pandas as pd
from datetime import datetime, timedelta
from src.energy_estimator import EnergyEstimator

# Detect hardware and get battery capacity
estimator = EnergyEstimator()
hw_model = estimator.hw_model
battery_wh = estimator.battery_wh
battery_mah = estimator.battery_mah

print(f"\n{'='*70}")
print(f"Energy Validation Report")
print(f"{'='*70}")
print(f"Hardware Model: {hw_model}")
print(f"Battery Capacity: {battery_wh}Wh ({battery_mah:.0f}mAh)")
print(f"{'='*70}\n")

# Load energy log
try:
    df = pd.read_csv('data/energy_log.csv')
except FileNotFoundError:
    print("❌ Error: data/energy_log.csv not found")
    print("   Run 'poetry run app-energy collect' to generate data")
    exit(1)

if df.empty:
    print("❌ Error: energy_log.csv is empty")
    exit(1)

# Convert timestamp to datetime
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Filter to last 10 hours
cutoff_time = df['timestamp'].max() - timedelta(hours=10)
df_recent = df[df['timestamp'] >= cutoff_time].copy()

print(f"Total readings: {len(df)}")
print(f"Recent (last 10h): {len(df_recent)}")
print(f"Time range: {df_recent['timestamp'].min()} to {df_recent['timestamp'].max()}")
duration_hours = (df_recent['timestamp'].max() - df_recent['timestamp'].min()).total_seconds() / 3600
print(f"Duration: {duration_hours:.1f} hours\n")

# Group by app and sum energy
app_energy = df_recent.groupby('app_name')['estimated_energy_mah'].sum().sort_values(ascending=False)

print(f"Top 10 Apps by Energy Consumption:")
print(f"{'-'*70}")
for i, (app, energy) in enumerate(app_energy.head(10).items(), 1):
    pct = (energy / battery_mah) * 100
    print(f"{i:2d}. {app:30s} {energy:10.2f}mAh ({pct:5.2f}%)")

# Total energy calculation
total_energy_mah = df_recent['estimated_energy_mah'].sum()
calculated_drain_pct = (total_energy_mah / battery_mah) * 100

print(f"\n{'-'*70}")
print(f"Total energy consumed: {total_energy_mah:.2f}mAh")
print(f"Battery capacity: {battery_mah:.0f}mAh")
print(f"Calculated drain: {calculated_drain_pct:.2f}%")
print(f"{'-'*70}\n")

# Data quality checks
print(f"Data Quality Metrics:")
print(f"{'-'*70}")
zero_readings = (df_recent['estimated_power_mw'] == 0).sum()
print(f"Zero power readings: {zero_readings}")
max_power_w = df_recent['estimated_power_mw'].max() / 1000
avg_power_w = df_recent['estimated_power_mw'].mean() / 1000
median_power_w = df_recent['estimated_power_mw'].median() / 1000
print(f"Max power draw: {max_power_w:.2f}W")
print(f"Avg power draw: {avg_power_w:.2f}W")
print(f"Median power draw: {median_power_w:.2f}W")

# Battery drain reference
print(f"\n{'-'*70}")
print(f"Expected vs Actual:")
print(f"{'-'*70}")
print(f"Calculated drain: {calculated_drain_pct:.2f}%")
print(f"(Compare to your actual battery change: e.g., 80% → 67% = 13%)")
print(f"\nIf these don't match, the battery capacity may need adjustment.")
print(f"{'='*70}\n")
