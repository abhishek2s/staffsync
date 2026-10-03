import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "config" / ".env")

from config.settings import settings
from src.synthesizer import DataSynthesizer
from src.loader import BronzeLoader
from src.db_manager import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger("PipelineOrchestrator")


def run():
    logger.info("Initializing StaffSync Data Engineering Pipeline...")
    try:
        # # ---------------------------------------------------------------------
        # # PHASE 1: BRONZE STAGING LAYER
        # # ---------------------------------------------------------------------
        # logger.info("--- PHASE 1: BRONZE STAGING INGESTION ---")
        
        # logger.info("Step 1.1: Running Data Synthesizer (Generating 5 CSVs)...")
        # synthesizer = DataSynthesizer()
        # shapes = synthesizer.run()
        # logger.info(f"Generated synthetic datasets: {list(shapes.keys())}")

        # logger.info("Step 1.2: Loading CSVs into MySQL Bronze Staging Schema...")
        # loader = BronzeLoader()
        # loader.run()

        # ---------------------------------------------------------------------
        # PHASE 2: SILVER 3NF OLTP LAYER
        # ---------------------------------------------------------------------
        logger.info("--- PHASE 2: SILVER 3NF OLTP TRANSFORMATION ---")
        
        db_mgr = DatabaseManager()
        
        logger.info("Step 2.1: Executing `sp_populate_oltp()` migration stored procedure...")
        db_mgr.execute_procedure(
            schema=settings.DB.SILVER_SCHEMA,
            procedure_name="sp_populate_oltp"
        )

        logger.info("Pipeline execution completed successfully across Bronze and Silver layers!")

    except Exception as exc:
        logger.critical(f"Pipeline execution failed due to exception: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()