import asyncio
import logging
import os
import sys
from pathlib import Path

from sqlalchemy import text

# --- Path Configuration ---
current_script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(current_script_path)
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)
# --- End Path Configuration ---

# Now, safe to import project modules
from src.database.database import AsyncSessionLocal
from scripts.import_tutorial_data import process_document, gemini_service

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


async def clear_tutorial_tables():
    """Connects to the database and truncates the tutorial tables."""
    log.info("Connecting to the database to clear tutorial tables...")
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                log.info("Executing TRUNCATE on tutorials.knowledge_chunks...")
                await session.execute(
                    text(
                        "TRUNCATE TABLE tutorials.knowledge_chunks RESTART IDENTITY CASCADE"
                    )
                )
                log.info("Executing TRUNCATE on tutorials.tutorial_documents...")
                await session.execute(
                    text(
                        "TRUNCATE TABLE tutorials.tutorial_documents RESTART IDENTITY CASCADE"
                    )
                )
            log.info("Successfully cleared tutorial tables.")
            return True
    except Exception as e:
        log.error(f"An error occurred while clearing tables: {e}", exc_info=True)
        return False


async def main():
    """Main function to clear and re-import tutorial data."""
    log.info("--- Starting Tutorial Database Reset and Re-import Process ---")

    # Step 1: Clear the existing tables
    success = await clear_tutorial_tables()
    if not success:
        log.error("Aborting re-import process due to failure in clearing tables.")
        return

    # Step 2: Re-import the document
    if not gemini_service.is_available():
        log.error("Gemini service is not available. Check API keys. Aborting.")
        return

    document_to_import = Path("docs/tutorial_rag_feature_plan.md")
    log.info(f"Starting re-import of document: '{document_to_import}'")
    try:
        async with AsyncSessionLocal() as session:
            await process_document(session, document_to_import)
        log.info(
            "--- Tutorial Database Reset and Re-import Process Finished Successfully ---"
        )
    except Exception as e:
        log.error(f"An error occurred during the re-import process: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
