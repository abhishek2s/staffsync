from __future__ import annotations

import os
from typing import Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from config.settings import settings
from src.utils.logger import setup_logger

logger = setup_logger("DatabaseManager")


class DatabaseManager:
    _instance: Optional[DatabaseManager] = None
    _engines: dict[str, Engine] = {}

    def __new__(cls) -> DatabaseManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        self.host = settings.DB.HOST
        self.port = settings.DB.PORT
        self.user = settings.DB.USER
        self.password = settings.DB.PASSWORD

    def get_engine(self, schema: str) -> Engine:
        if schema not in self._engines:
            url = (
                f"mysql+pymysql://{quote_plus(self.user)}:{quote_plus(self.password)}"
                f"@{self.host}:{self.port}/{schema}"
            )
            self._engines[schema] = create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)
            logger.info(f"Initialized Database Engine for schema: `{schema}`")
        return self._engines[schema]

    def execute_procedure(self, schema: str, procedure_name: str) -> None:
        """Executes a stored procedure inside a specific database schema."""
        engine = self.get_engine(schema)
        logger.info(f"Executing stored procedure `{schema}.{procedure_name}()`...")
        try:
            with engine.begin() as conn:
                conn.execute(text(f"CALL {procedure_name}();"))
            logger.info(f"Successfully executed procedure `{schema}.{procedure_name}()`.")
        except SQLAlchemyError as err:
            logger.error(f"Error executing procedure `{procedure_name}`: {err}")
            raise