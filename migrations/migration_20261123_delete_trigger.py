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
            for row in conn.execute("PRAGMA table_info(hourly)")
        }

        # Drop triggers if they exist
        conn.execute("DROP TRIGGER IF EXISTS update_samples_timestamp")
        conn.execute("DROP TRIGGER IF EXISTS update_hourly_timestamp")

        # Continue migration...

migrate(DB_PATH)