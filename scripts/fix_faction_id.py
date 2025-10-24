import asyncio
import logging
import os
import sys

# Add project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.chat.utils.database import chat_db_manager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def fix_faction_ids():
    """
    Corrects the faction_id from 'zombie' to 'jiangshi' in the database tables.
    """
    db = chat_db_manager
    await db.connect()

    updated_faction_points = 0
    updated_contribution_logs = 0

    try:
        # Use a transaction to ensure atomicity
        async with db._db_transaction.connection.transaction():
            logging.info("Starting data migration for faction IDs...")

            # 1. Update event_faction_points table
            logging.info("Updating 'event_faction_points' table...")
            points_query = "UPDATE event_faction_points SET faction_id = 'jiangshi' WHERE faction_id = 'zombie';"
            result_points = await db._execute(
                db._db_transaction, points_query, commit=False
            )
            updated_faction_points = result_points if result_points is not None else 0
            logging.info(
                f"Updated {updated_faction_points} records in 'event_faction_points'."
            )

            # 2. Update event_contribution_log table
            logging.info("Updating 'event_contribution_log' table...")
            log_query = "UPDATE event_contribution_log SET faction_id = 'jiangshi' WHERE faction_id = 'zombie';"
            result_logs = await db._execute(db._db_transaction, log_query, commit=False)
            updated_contribution_logs = result_logs if result_logs is not None else 0
            logging.info(
                f"Updated {updated_contribution_logs} records in 'event_contribution_log'."
            )

        logging.info("Transaction committed successfully.")

    except Exception as e:
        logging.error(f"An error occurred during the migration: {e}", exc_info=True)
        logging.error("Transaction was rolled back.")
    finally:
        await db.disconnect()
        logging.info("Database connection closed.")

    logging.info("--- Migration Summary ---")
    logging.info(
        f"Total records updated in 'event_faction_points': {updated_faction_points}"
    )
    logging.info(
        f"Total records updated in 'event_contribution_log': {updated_contribution_logs}"
    )
    logging.info("Migration script finished.")


if __name__ == "__main__":
    asyncio.run(fix_faction_ids())
