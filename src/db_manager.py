from contextlib import contextmanager
from time import perf_counter
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text

from config.settings import settings
from src.utils.logger import setup_logger

logger = setup_logger("DatabaseManager")


class DatabaseManager:
    SILVER = settings.DB.SILVER_SCHEMA   # OLTP
    GOLD = settings.DB.GOLD_SCHEMA       # OLAP

    RELAX_PRIMARY_KEY_RULE = True

    _instances = {}
    _engines = {}

    def __new__(cls):
        if cls not in cls._instances:
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

    def get_engine(self, schema):
        """Create (once) and return the connection pool for a schema."""
        if schema not in DatabaseManager._engines:
            db = settings.DB
            url = (f"mysql+pymysql://{quote_plus(db.USER)}:{quote_plus(db.PASSWORD)}"
                   f"@{db.HOST}:{db.PORT}/{schema}")
            DatabaseManager._engines[schema] = create_engine(
                url, pool_pre_ping=True, pool_size=10, max_overflow=20)
            logger.info(f"Connected to schema `{schema}`")
        return DatabaseManager._engines[schema]


    @contextmanager
    def connection(self, schema):
        """Borrow a connection for READING."""
        with self.get_engine(schema).connect() as conn:
            yield conn

    @contextmanager
    def transaction(self, schema):
        """Borrow a connection for WRITING under ONE transaction."""
        with self.get_engine(schema).begin() as conn:
            if self.RELAX_PRIMARY_KEY_RULE:
                conn.execute(text("SET SESSION sql_require_primary_key = 0;"))
            yield conn

    @contextmanager
    def operation(self, label):
        """Log operation lifecycle and timing."""
        started = perf_counter()
        logger.info(f"{label} - started")
        try:
            yield
        except Exception as err:
            logger.error(f"{label} - FAILED after {perf_counter() - started:.2f}s: {err}")
            raise
        logger.info(f"{label} - done in {perf_counter() - started:.2f}s")


    def read(self, schema, sql, params=None, conn=None):
        """Run a SELECT and return a pandas DataFrame."""
        if conn is not None:
            return pd.read_sql(text(sql), conn, params=params or {})
        with self.get_engine(schema).connect() as connection:
            return pd.read_sql(text(sql), connection, params=params or {})

    def read_one(self, schema, sql, params=None, conn=None):
        """Run a SELECT and return the first row as a dict."""
        if conn is not None:
            row = conn.execute(text(sql), params or {}).mappings().first()
            return dict(row) if row else None
        with self.get_engine(schema).connect() as connection:
            row = connection.execute(text(sql), params or {}).mappings().first()
            return dict(row) if row else None

    def write(self, schema, sql, params=None, conn=None):
        """Run INSERT / UPDATE / DELETE."""
        if conn is not None:
            return conn.execute(text(sql), params or {}).rowcount
        with self.transaction(schema) as new_conn:
            return new_conn.execute(text(sql), params or {}).rowcount

    def execute_procedure(self, schema, procedure_name):
        """Executes a stored procedure."""
        with self.operation(f"procedure {schema}.{procedure_name}()"):
            with self.transaction(schema) as conn:
                conn.execute(text(f"CALL {procedure_name}();"))


DatabaseConnection = DatabaseManager