from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from config.settings import settings
from src.utils.logger import setup_logger

logger = setup_logger("BronzeLoader")

DATE_COLUMNS = {
    "stg_employee": ["hire_date", "effective_from"],
    "stg_employee_history": ["valid_from", "valid_to"],
    "stg_project": ["start_date", "planned_end_date"],
    "stg_assignment": ["assigned_date"],
    "stg_review": ["review_date"],
}


class BronzeLoader:
    def __init__(self) -> None:
        self.host = settings.DB.HOST
        self.port = settings.DB.PORT
        self.user = settings.DB.USER
        self.password = settings.DB.PASSWORD
        self.schema = settings.DB.BRONZE_SCHEMA
        self.data_dir = settings.PATHS.DATA_DIR

    def _engine(self):
        url = (
            f"mysql+pymysql://{quote_plus(self.user)}:{quote_plus(self.password)}"
            f"@{self.host}:{self.port}/{self.schema}"
        )
        return create_engine(url, pool_pre_ping=True)

    def truncate_table(self, engine, table: str) -> None:
        """Truncates the target table to wipe existing data before loading new records."""
        logger.info(f"Clearing existing rows in `{self.schema}.{table}`...")
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE `{table}`;"))

    def load_table(self, engine, table: str) -> int:
        path = self.data_dir / f"{table}.csv"
        if not path.exists():
            logger.error(f"Cannot find CSV at {path}")
            raise FileNotFoundError(f"{path} not found.")

        # Wipe old data before inserting fresh records
        self.truncate_table(engine, table)

        logger.info(f"Ingesting {path} into `{self.schema}.{table}`...")
        total = 0
        try:
            for chunk in pd.read_csv(path, parse_dates=DATE_COLUMNS[table], chunksize=20_000):
                chunk.to_sql(
                    table,
                    engine,
                    if_exists="append",
                    index=False,
                    method="multi",
                    chunksize=1_000,
                )
                total += len(chunk)
            logger.info(f"Successfully loaded {total:,} rows into table `{table}`.")
            return total
        except SQLAlchemyError as err:
            logger.error(f"Error loading table {table}: {err}")
            raise

    def run(self) -> None:
        engine = self._engine()
        for table in DATE_COLUMNS:
            self.load_table(engine, table)
        logger.info("All 5 staging tables loaded fresh into MySQL Bronze Database.")