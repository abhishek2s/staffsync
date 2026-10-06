"""Entry point for the StaffSync data pipeline."""

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "config" / ".env")

from config.settings import settings
from src.db_manager import DatabaseManager
from src.loader import BronzeLoader
from src.synthesizer import DataSynthesizer
from src.utils.logger import setup_logger

logger = setup_logger("PipelineOrchestrator")


def run() -> None:
    """Run the bronze, silver, and gold pipeline stages."""
    logger.info("Initializing StaffSync data engineering pipeline.")

    try:
        # logger.info("Phase 1: Bronze staging ingestion")
        # logger.info("Step 1.1: Running Data Synthesizer to generate synthetic datasets.")
        # synthesizer = DataSynthesizer()
        # shapes = synthesizer.run()
        # logger.info("Generated synthetic datasets: %s", list(shapes.keys()))

        # logger.info("Step 1.2: Loading generated CSV files into the MySQL bronze schema.")
        # loader = BronzeLoader()
        # loader.run()

        logger.info("Phase 2: Silver 3NF OLTP transformation")
        db_mgr = DatabaseManager()
        logger.info("Step 2.1: Executing the sp_populate_oltp stored procedure.")
        db_mgr.execute_procedure(
            schema=settings.DB.SILVER_SCHEMA,
            procedure_name="sp_populate_oltp",
        )

        logger.info("Phase 3: Gold dimensional OLAP transformation")
        logger.info("Step 3.1: Executing the sp_populate_olap warehouse load.")
        db_mgr.execute_procedure(
            schema=settings.DB.GOLD_SCHEMA,
            procedure_name="sp_populate_olap",
        )

        logger.info("Pipeline completed successfully across bronze, silver, and gold layers.")
    except Exception as exc:
        logger.critical("Pipeline execution failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
