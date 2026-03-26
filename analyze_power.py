#!/usr/bin/env python3
"""Analyze power values per sample."""

import pandas as pd

df = pd.read_csv('data/energy_log.csv')

# Check first few samples
print(f"Total rows: {len(df)}")
print(f"Unique timestamps: {df['timestamp'].nunique()}")
print()

timestamps = df['timestamp'].unique()[:5]
for i, ts in enumerate(timestamps):
    df_sample = df[df['timestamp'] == ts]
    total_power_w = df_sample['estimated_power_mw'].sum() / 1000
    total_energy_mah = df_sample['estimated_energy_mah'].sum()
    num_procs = len(df_sample)
    print(f"Sample {i+1} ({ts}):")
    print(f"  Processes: {num_procs}")
    print(f"  Total power: {total_power_w:.2f}W")
    print(f"  Total energy: {total_energy_mah:.2f}mAh")
    print(f"  Avg power/process: {df_sample['estimated_power_mw'].mean():.2f}mW")
    print()
