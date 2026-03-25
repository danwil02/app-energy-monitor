"""Configuration settings for app energy monitor."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# InfluxDB Configuration
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "myorg")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "app_energy")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "")

# Collection Configuration
COLLECTION_INTERVAL = int(os.getenv("COLLECTION_INTERVAL", "60"))  # seconds
CSV_PATH = Path(os.getenv("CSV_PATH", "data/energy_log.csv"))
LOG_PATH = Path(os.getenv("LOG_PATH", "logs/daemon.log"))

# App Filtering
# Comma-separated list of app names to include (empty = all)
APP_WHITELIST = os.getenv("APP_WHITELIST", "").split(",") if os.getenv("APP_WHITELIST") else []
# Comma-separated list of app names to exclude
APP_BLACKLIST = os.getenv("APP_BLACKLIST", "").split(",") if os.getenv("APP_BLACKLIST") else [
    "kernel_task", "system", "loginwindow", "Finder"
]

# Ensure data directories exist
CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
