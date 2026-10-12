from __future__ import annotations

from pathlib import Path
import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from config.settings import settings
from src.db_manager import DatabaseManager
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
        self.db = DatabaseManager()
        self.schema = settings.DB.BRONZE_SCHEMA
        self.data_dir = settings.PATHS.DATA_DIR

    def truncate_table(self, conn, table: str) -> None:
        """Truncates the target table to wipe existing data before loading new records."""
        logger.info(f"Clearing existing rows in `{self.schema}.{table}`...")
        conn.execute(text(f"TRUNCATE TABLE `{table}`;"))

    def load_table(self, conn, table: str) -> int:
        path = self.data_dir / f"{table}.csv"
        if not path.exists():
            logger.error(f"Cannot find CSV at {path}")
            raise FileNotFoundError(f"{path} not found.")

        # Wipe old data before inserting fresh records using the shared transaction connection
        self.truncate_table(conn, table)

        logger.info(f"Ingesting {path} into `{self.schema}.{table}`...")
        total = 0
        try:
            for chunk in pd.read_csv(path, parse_dates=DATE_COLUMNS.get(table, []), chunksize=20_000):
                chunk.to_sql(
                    name=table,
                    con=conn,
                    schema=self.schema,
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
        logger.info(f"Starting Bronze bulk ingestion for schema `{self.schema}`...")
        
        # Borrow a single write transaction connection from DatabaseManager
        with self.db.transaction(self.schema) as conn:
            # SET SESSION sql_require_primary_key = 0;
            for table in DATE_COLUMNS:
                self.load_table(conn, table)
                
        logger.info("All staging tables loaded fresh into Bronze Database under a unified transaction.")