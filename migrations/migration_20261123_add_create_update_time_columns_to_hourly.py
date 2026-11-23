import os
import sqlite3
from contextlib import asynccontextmanager, closing
from dotenv import load_dotenv
load_dotenv()

DB_PATH = os.getenv("PLUG_DB", "plug.db")

def migrate(db_path: str):
    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(hourly)"
            )
        }

        if "create_time" not in columns:
            conn.execute("""
                ALTER TABLE hourly
                ADD COLUMN create_time DATETIME
            """)

        if "update_time" not in columns:
            conn.execute("""
                ALTER TABLE hourly
                ADD COLUMN update_time DATETIME
            """)

        conn.execute("""
            UPDATE hourly
            SET
                create_time = COALESCE(create_time, CURRENT_TIMESTAMP),
                update_time = COALESCE(update_time, CURRENT_TIMESTAMP)
            WHERE create_time IS NULL OR update_time IS NULL
        """)

        conn.executescript("""
                DROP TRIGGER IF EXISTS update_hourly_timestamp;

                CREATE TRIGGER update_hourly_timestamp
                AFTER UPDATE ON hourly
                FOR EACH ROW
                WHEN NEW.update_time = OLD.update_time
                BEGIN
                    UPDATE hourly
                    SET update_time = CURRENT_TIMESTAMP
                    WHERE ts = NEW.ts;
                END;
            """)

migrate(DB_PATH)