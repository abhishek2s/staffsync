"""Application-wide configuration for StaffSync."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "config" / ".env")


class DatabaseConfig:
    """MySQL connection settings for each medallion layer."""

    HOST: str = os.getenv("DB_HOST", "localhost")
    PORT: int = int(os.getenv("DB_PORT", 3306))
    USER: str = os.getenv("DB_USER", "root")
    PASSWORD: str = os.getenv("DB_PASSWORD", "")
    BRONZE_SCHEMA: str = os.getenv("DB_NAME_BRONZE", "staffsync_bronze")
    SILVER_SCHEMA: str = os.getenv("DB_NAME_SILVER", "staffsync_silver")
    GOLD_SCHEMA: str = os.getenv("DB_NAME_GOLD", "staffsync_gold")


class PathConfig:
    """Project directory and data paths."""

    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / os.getenv("DATA_DIR", "data/synthetic")
    RAW_DATA_PATH: Path = BASE_DIR / os.getenv("RAW_DATA_PATH", "data/raw/WA_Fn-UseC_-HR-Employee-Attrition.csv")
    LOG_DIR: Path = BASE_DIR / "logs"


class AppSettings:
    """Central settings singleton for the application."""

    DB = DatabaseConfig()
    PATHS = PathConfig()


settings = AppSettings()