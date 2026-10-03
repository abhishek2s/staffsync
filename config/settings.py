import os
from pathlib import Path
from dotenv import load_dotenv

# Define root project directory (staffsync/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Load configuration from the project root and the config folder.
# The environment file is stored under config/.env, not in the workspace root.
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "config" / ".env")


class DatabaseConfig:
    """MySQL Database Configuration for Medallion Layers."""
    HOST: str = os.getenv("DB_HOST", "localhost")
    PORT: int = int(os.getenv("DB_PORT", 3306))
    USER: str = os.getenv("DB_USER", "root")
    PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # Medallion Architecture Schemas
    BRONZE_SCHEMA: str = os.getenv("DB_NAME_BRONZE", "staffsync_bronze")
    SILVER_SCHEMA: str = os.getenv("DB_NAME_SILVER", "staffsync_silver")
    GOLD_SCHEMA: str = os.getenv("DB_NAME_GOLD", "staffsync_gold")


class PathConfig:
    """Project File and Directory Paths."""
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / os.getenv("DATA_DIR", "data/synthetic")
    RAW_DATA_PATH: Path = BASE_DIR / os.getenv("RAW_DATA_PATH", "data/raw/WA_Fn-UseC_-HR-Employee-Attrition.csv")
    LOG_DIR: Path = BASE_DIR / "logs"


class AppSettings:
    """Central Application Settings Singleton."""
    DB = DatabaseConfig()
    PATHS = PathConfig()


# Single exported settings object used across the entire application
settings = AppSettings()