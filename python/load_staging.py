"""
Load the synthesized CSVs into the MySQL `staging` schema.

Usage (local MySQL)
    set DB_PASSWORD=yourpassword            (Windows)   or   export DB_PASSWORD=yourpassword
    python load_staging.py --host localhost --user root

If DB_PASSWORD is not set you will be prompted for it. Never hardcode passwords
or commit them to GitHub.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from getpass import getpass
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from dotenv import load_dotenv
load_dotenv()

DATE_COLUMNS = {
    "stg_employee": ["hire_date", "effective_from"],
    "stg_employee_history": ["valid_from", "valid_to"],
    "stg_project": ["start_date", "planned_end_date"],
    "stg_assignment": ["assigned_date"],
    "stg_review": ["review_date"],
}
INDEX_COLUMNS = {
    "stg_employee": ["employee_id"],
    "stg_employee_history": ["employee_id"],
    "stg_project": ["project_id"],
    "stg_assignment": ["employee_id", "project_id"],
    "stg_review": ["employee_id", "project_id"],
}


class StagingLoader:
    def __init__(self, host, port, user, password, schema="staging",
                 data_dir="data/synthetic", ssl_ca=None):
        self.host, self.port, self.user, self.password = host, port, user, password
        self.schema = schema
        self.data_dir = Path(data_dir)
        self.ssl_ca = ssl_ca

    def _engine(self, database: str = ""):
        url = (
            f"mysql+pymysql://{quote_plus(self.user)}:{quote_plus(self.password)}"
            f"@{self.host}:{self.port}/{database}"
        )
        connect_args = {"ssl": {"ca": self.ssl_ca}} if self.ssl_ca else {}
        return create_engine(url, connect_args=connect_args, pool_pre_ping=True)

    def create_schema(self) -> None:
        engine = self._engine()
        with engine.begin() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{self.schema}`"))

    def load_table(self, engine, table: str) -> int:
        path = self.data_dir / f"{table}.csv"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found. Run data_synthesizer.py first.")
        total, first = 0, True
        for chunk in pd.read_csv(path, parse_dates=DATE_COLUMNS[table], chunksize=20_000):
            chunk.to_sql(
                table, engine, if_exists="replace" if first else "append",
                index=False, method="multi", chunksize=1_000,
            )
            first = False
            total += len(chunk)
        return total

    def create_indexes(self, engine) -> None:
        with engine.begin() as conn:
            for table, columns in INDEX_COLUMNS.items():
                for col in columns:
                    conn.execute(text(f"CREATE INDEX idx_{table}_{col} ON `{table}` (`{col}`)"))

    def verify(self, engine) -> None:
        print("\nRow counts in MySQL:")
        with engine.connect() as conn:
            for table in DATE_COLUMNS:
                count = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
                print(f"  {self.schema}.{table:<22}{count:>10,}")

    def run(self) -> None:
        self.create_schema()
        engine = self._engine(self.schema)
        for table in DATE_COLUMNS:
            t0 = time.time()
            rows = self.load_table(engine, table)
            print(f"Loaded {table:<22}{rows:>10,} rows in {time.time() - t0:.1f}s", flush=True)
        self.create_indexes(engine)
        self.verify(engine)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load synthetic CSVs into MySQL staging")
    parser.add_argument("--host", default=os.getenv("DB_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("DB_PORT", "3306")))
    parser.add_argument("--user", default=os.getenv("DB_USER", "root"))
    parser.add_argument("--schema", default="staging")
    parser.add_argument("--data-dir", default="data/synthetic")
    parser.add_argument("--ssl-ca", default=os.getenv("DB_SSL_CA"))
    args = parser.parse_args()

    password = os.getenv("DB_PASSWORD") or getpass("MySQL password: ")
    try:
        StagingLoader(args.host, args.port, args.user, password,
                      args.schema, args.data_dir, args.ssl_ca).run()
    except (SQLAlchemyError, FileNotFoundError) as exc:
        print(f"Load failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()