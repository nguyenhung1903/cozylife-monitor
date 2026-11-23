import os
import sqlite3
from contextlib import asynccontextmanager, closing
from dotenv import load_dotenv
load_dotenv()

DB_PATH = os.getenv("PLUG_DB", "plug.db")
def migrate(db_path: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_lifecycle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shutdown_time REAL NOT NULL,
                startup_time REAL NOT NULL,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(system_lifecycle)"
            )
        }

        if "create_time" not in columns:
            conn.execute("""
                ALTER TABLE system_lifecycle
                ADD COLUMN create_time DATETIME
            """)

        if "update_time" not in columns:
            conn.execute("""
                ALTER TABLE system_lifecycle
                ADD COLUMN update_time DATETIME
            """)

        conn.execute("""
            UPDATE system_lifecycle
            SET
                create_time = COALESCE(create_time, CURRENT_TIMESTAMP),
                update_time = COALESCE(update_time, CURRENT_TIMESTAMP)
            WHERE create_time IS NULL OR update_time IS NULL
        """)

migrate(DB_PATH)