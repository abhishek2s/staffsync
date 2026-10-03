"""
db_manager.py  -  the ONLY place that talks to MySQL.

Two ideas used here:
1. SINGLETON  : no matter how many times you write DatabaseManager(), you get the
                SAME object back. This stops the app from opening hundreds of
                connections.
2. INHERITANCE: our Manager classes (EmployeeManager, ...) extend this class, so
                they get read() / write() for free.
"""
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text

from config.settings import settings
from src.utils.logger import setup_logger

logger = setup_logger("DatabaseManager")


class DatabaseManager:
    # Schema names (bronze / silver / gold) come from your settings file
    SILVER = settings.DB.SILVER_SCHEMA   # OLTP  - the app writes here
    GOLD = settings.DB.GOLD_SCHEMA       # OLAP  - dashboards read from here

    _instances = {}   # remembers the one object created for each class
    _engines = {}     # remembers one connection pool per schema

    # __new__ runs BEFORE __init__ and decides which object to hand back.
    def __new__(cls):
        if cls not in cls._instances:                       # first time?
            cls._instances[cls] = super().__new__(cls)      # create it
        return cls._instances[cls]                          # always return the same one

    def get_engine(self, schema):
        """Create (once) and return the connection for a schema."""
        if schema not in DatabaseManager._engines:
            db = settings.DB
            url = (f"mysql+pymysql://{quote_plus(db.USER)}:{quote_plus(db.PASSWORD)}"
                   f"@{db.HOST}:{db.PORT}/{schema}")
            DatabaseManager._engines[schema] = create_engine(
                url, pool_pre_ping=True, pool_size=10, max_overflow=20)
            logger.info(f"Connected to schema `{schema}`")
        return DatabaseManager._engines[schema]

    def read(self, schema, sql, params=None):
        """Run a SELECT and return a pandas DataFrame (great for Streamlit charts)."""
        with self.get_engine(schema).connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})

    def read_one(self, schema, sql, params=None):
        """Run a SELECT and return the first row as a dict (or None if no rows)."""
        with self.get_engine(schema).connect() as conn:
            row = conn.execute(text(sql), params or {}).mappings().first()
            return dict(row) if row else None

    def write(self, schema, sql, params=None):
        """Run INSERT / UPDATE / DELETE. Saved automatically; returns rows changed."""
        with self.get_engine(schema).begin() as conn:   # begin() = auto commit
            return conn.execute(text(sql), params or {}).rowcount

    def execute_procedure(self, schema, procedure_name):
        """Run a stored procedure, e.g. sp_scd2_update."""
        with self.get_engine(schema).begin() as conn:
            conn.execute(text(f"CALL {procedure_name}();"))
        logger.info(f"Ran procedure {schema}.{procedure_name}()")


# The project brief calls this class "DatabaseConnection", so keep both names.
DatabaseConnection = DatabaseManager