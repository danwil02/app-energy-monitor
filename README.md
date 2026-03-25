# App Energy Monitor

TLDR: My laptop died today and I wanted to understand which apps were consuming the most energy. I built this tool to fill the gap in macOS for per-app energy monitoring. It uses `powermetrics` to get system-level power data and correlates it with process metrics from `psutil` to estimate energy consumption for each app.

---

**💡 Found this useful?** Consider buying me a beer! Your support helps me maintain this project.

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-FFDD00?style=flat&logo=buy-me-a-coffee)](https://buymeacoffee.com/willdaniels)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Donate-FF5E62?style=flat&logo=ko-fi)](https://ko-fi.com/willdaniels)
[![GitHub Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-Support-white?style=flat&logo=github)](https://github.com/sponsors/willdaniels)

---

## Features

- Per-app CPU, memory, and I/O tracking
- System-level power correlation with `powermetrics` (requires sudo)
- Energy estimation via attribution algorithm
- CSV export and InfluxDB integration
- Continuous daemon mode and CLI interface
- Fallback to estimation-only mode if `powermetrics` is unavailable

## Installation

```bash
poetry install
```

## Usage

### Basic Collection (estimation mode - no sudo required)

```bash
poetry run app-energy collect --output table --top 10
```

### With Full Power Data (requires sudo)

For more accurate power measurements, run with sudo:

```bash
sudo poetry run app-energy collect --output table --top 10
sudo poetry run app-energy daemon --interval 60 --output both
```

### Configure Passwordless Sudo (Optional)

To avoid entering your password every time, configure passwordless sudo for powermetrics:

```bash
sudo visudo
```

Add this line at the end:
```
%admin ALL=(ALL) NOPASSWD: /usr/bin/powermetrics
```

### Available Commands

- **collect** - Single measurement and output to table/CSV/InfluxDB
  ```bash
  poetry run app-energy collect --output table --top 5
  poetry run app-energy collect --output csv
  poetry run app-energy collect --output both
  ```

- **daemon** - Continuous background monitoring
  ```bash
  poetry run app-energy daemon --interval 60 --output both
  poetry run app-energy daemon --interval 60 --duration 120  # Run for 2 hours
  ```

- **report** - Analyze CSV data
  ```bash
  poetry run app-energy report --hours 1 --top 10
  ```

- **status** - Show current configuration
  ```bash
  poetry run app-energy status
  ```

## Configuration

Create a `.env` file in the project root (copy from `config/.env.example`):

```bash
cp config/.env.example .env
```

Then edit `.env` with your settings:

```env
# InfluxDB Configuration
INFLUXDB_URL=http://localhost:8086
INFLUXDB_ORG=myorg
INFLUXDB_BUCKET=app_energy
INFLUXDB_TOKEN=your-token-here

# Collection Configuration
COLLECTION_INTERVAL=60
CSV_PATH=data/energy_log.csv
LOG_PATH=logs/daemon.log

# App Filtering
APP_WHITELIST=
APP_BLACKLIST=kernel_task,system,loginwindow,Finder
```

## How It Works

1. **Process Collection**: Uses `psutil` to gather CPU time, memory, and I/O metrics for all running processes
2. **System Power Measurement**: Calls `powermetrics` (with sudo) to get system-level power consumption
3. **Energy Attribution**: Estimates per-app energy by correlating process metrics with system power using:
   - CPU time ratio (60% weight)
   - Memory usage ratio (10% weight)
   - I/O operations ratio (20% weight)
   - Thread count ratio (10% weight)
4. **Storage**: Writes data to CSV files and/or InfluxDB for analysis

## Energy Estimation Model

The energy estimation algorithm attributes system-level power consumption to individual applications based on their resource utilization. This section describes the underlying mathematical model.

### Metric Attribution

For each running process, four resource utilization fractions are calculated relative to total system resource consumption:

**CPU Fraction:**
$$f_{cpu,i} = \frac{\text{CPU}_{\text{user},i} + \text{CPU}_{\text{system},i}}{\sum_j (\text{CPU}_{\text{user},j} + \text{CPU}_{\text{system},j})}$$

**Memory Fraction:**
$$f_{mem,i} = \frac{\text{Memory}_{rss,i}}{\sum_j \text{Memory}_{rss,j}}$$

**I/O Fraction:**
$$f_{io,i} = \frac{\text{I/O}_{\text{read},i} + \text{I/O}_{\text{write},i}}{\sum_j (\text{I/O}_{\text{read},j} + \text{I/O}_{\text{write},j})}$$

**Wakeup/Thread Fraction:**
$$f_{wake,i} = \frac{\text{Threads}_{i}}{\sum_j \text{Threads}_{j}}$$

Where subscript $i$ denotes a specific process and the sum is over all running processes.

### Power Attribution

System-level power consumption is distributed to each process using a weighted combination of the resource fractions:

$$P_{app,i} = P_{system} \times \left( 0.6 \cdot f_{cpu,i} + 0.1 \cdot f_{mem,i} + 0.2 \cdot f_{io,i} + 0.1 \cdot f_{wake,i} \right)$$

Where:
- $P_{system}$ = Total system power consumption in milliwatts (mW), from `powermetrics`
- $P_{app,i}$ = Estimated power for application $i$ in milliwatts
- Weights (0.6, 0.1, 0.2, 0.1) represent the relative importance of each resource type in power consumption

**Weight Rationale:**
- **CPU (60%)**: Dominant power consumer, especially in modern systems
- **I/O (20%)**: Significant power cost for storage and network operations
- **Memory (10%)**: Secondary power cost from DRAM access patterns
- **Threads/Wakeups (10%)**: Scheduling overhead and interrupt handling

### Energy Calculation

Power is integrated over the sampling interval to calculate energy. Since we collect metrics at discrete time intervals, energy is calculated as:

$$E_{app,i} = \int_0^{\Delta t} P_{app,i}(t) \, dt \approx P_{app,i} \times \Delta t$$

For the battery charge representation (milliamp-hours), we convert power using Ohm's law:

$$I = \frac{P}{V}$$

Therefore:

$$E_{app,i}[\text{mAh}] = \frac{P_{app,i}[\text{mW}]}{V[\text{V}]} \times \frac{\Delta t[\text{s}]}{3600[\text{s/h}]}$$

Where:
- $P_{app,i}$ = Power in milliwatts
- $V$ = Battery voltage (typical macOS device: 15V)
- $\Delta t$ = Sampling interval in seconds
- Energy is expressed in milliamp-hours (mAh)

### System Power Estimation (Fallback Mode)

When `powermetrics` is unavailable, the system power is estimated using a simple linear model:

$$P_{system} \approx 5000 + \frac{\sum_j (\text{CPU}_{\text{user},j} + \text{CPU}_{\text{system},j})}{100}$$

This provides a baseline estimate where:
- 5000 mW represents idle power (~5W, typical for macOS systems)
- The second term linearly scales with total CPU activity

### Example Calculation

Given a sampling interval of 60 seconds:
- System power: 8000 mW (from `powermetrics`)
- Process A: CPU time 500 ms, total CPU time 2000 ms → $f_{cpu,A} = 0.25$
- Process A: Memory 400 MB, total memory 4000 MB → $f_{mem,A} = 0.1$
- Process A: I/O bytes 50 MB, total I/O 500 MB → $f_{io,A} = 0.1$
- Process A: Threads 8, total threads 100 → $f_{wake,A} = 0.08$

Power attribution:
$$P_A = 8000 \times (0.6 \times 0.25 + 0.1 \times 0.1 + 0.2 \times 0.1 + 0.1 \times 0.08) = 8000 \times 0.188 = 1504 \text{ mW}$$

Energy in 60 seconds with 15V battery:
$$E_A = \frac{1504}{15} \times \frac{60}{3600} = 100.27 \text{ mAh}$$

## Known Limitations

- **Per-app energy estimation**: Since macOS doesn't expose per-app energy via public APIs, we use correlation and attribution algorithms. This gives reasonable relative rankings but may not be absolute values.
- **powermetrics dependency**: Full power measurement requires `powermetrics`, which needs superuser privileges
- **Fallback mode**: If `powermetrics` is unavailable, the app falls back to process-level estimation only (no system power baseline)
- **I/O measurements**: I/O counters are not available for all processes on macOS

## Testing

Run the test suite:

```bash
poetry run pytest tests/ -v
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. By contributing to this project, you agree that your contributions will be licensed under the same Community License.

## Support

If you find this project helpful and would like to support its development:

- ⭐ Star the repository on GitHub
- 🐛 Report bugs and suggest features via Issues
- 💰 [Buy Me a Coffee](https://buymeacoffee.com/willdaniels) or [Ko-fi](https://ko-fi.com/willdaniels) to support ongoing development
- 💼 Reach out if you need commercial licensing or support

## Project Structure

```
app-energy-monitor/
├── src/
│   ├── __init__.py
│   ├── cli.py              # Click CLI commands
│   ├── collector.py        # Process metrics collection
│   ├── config.py           # Configuration management
│   ├── energy_estimator.py # Energy attribution algorithm
│   ├── logger.py           # Rich logging utility
│   ├── models.py           # Data models
│   ├── powermetrics_parser.py  # System power parser
│   ├── csv_writer.py       # CSV storage
│   └── storage.py          # InfluxDB storage
├── tests/
│   ├── __init__.py
│   └── test_energy_monitor.py
├── config/
│   └── .env.example
├── data/
│   ├── energy_log.csv
│   └── system_power.csv
├── logs/
│   └── daemon.log
├── pyproject.toml
├── README.md
├── LICENSE.COMMUNITY    # Personal use license
├── LICENSE.COMMERCIAL   # Commercial use license
├── FUNDING.yml          # GitHub sponsorship configuration
└── .gitignore
```

## License

This project is dual-licensed. Choose the license that best fits your use case:

### **Personal Use** (Free)
- **Community License**: Free to use for personal, educational, and non-commercial purposes
- See [LICENSE.COMMUNITY](LICENSE.COMMUNITY) for details

### **Commercial or Military Use** (Requires License)
- **Commercial License**: Required for any commercial, government, or military applications
- This includes:
  - SaaS or subscription services
  - Commercial products or plugins
  - Government or military use
  - Any revenue-generating use
- Contact: [danwil02@hotmail.com](mailto:danwil02@hotmail.com) for commercial licensing
- See [LICENSE.COMMERCIAL](LICENSE.COMMERCIAL) for details

**TL;DR**: For personal use, it's free with the Community License. For any commercial or military use, you'll need to purchase a commercial license.
