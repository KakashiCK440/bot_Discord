"""
Migration script to fix server_join_settings table schema.
Removes NOT NULL constraints from join_channel_id and admin_review_channel_id.
"""

import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "data/bot_data.db"

def migrate():
    """Migrate the server_join_settings table to remove NOT NULL constraints"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if the table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='server_join_settings'")
        if not cursor.fetchone():
            logger.info("Table server_join_settings doesn't exist yet. No migration needed.")
            conn.close()
            return
        
        # Get existing data
        cursor.execute("SELECT * FROM server_join_settings")
        existing_data = cursor.fetchall()
        
        logger.info(f"Found {len(existing_data)} existing rows")
        
        # Drop the old table
        cursor.execute("DROP TABLE IF EXISTS server_join_settings")
        logger.info("Dropped old table")
        
        # Create new table with correct schema
        cursor.execute("""
            CREATE TABLE server_join_settings (
                guild_id INTEGER PRIMARY KEY,
                join_channel_id INTEGER,
                admin_review_channel_id INTEGER,
                build_setup_channel_id INTEGER,
                min_power_requirement INTEGER DEFAULT 0,
                welcome_message_id INTEGER
            )
        """)
        logger.info("Created new table with updated schema")
        
        # Restore data
        if existing_data:
            cursor.executemany("""
                INSERT INTO server_join_settings 
                (guild_id, join_channel_id, admin_review_channel_id, min_power_requirement, welcome_message_id, build_setup_channel_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, existing_data)
            logger.info(f"Restored {len(existing_data)} rows")
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    migrate()
