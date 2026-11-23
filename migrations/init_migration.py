import os
import sqlite3
from contextlib import asynccontextmanager, closing
from dotenv import load_dotenv
load_dotenv()

DB_PATH = os.getenv("PLUG_DB", "plug.db")
def migrate(db_path: str):
    with sqlite3.connect(db_path) as conn:
        # system_lifecycle
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
        
        # hourly
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hourly (
                ts         INTEGER PRIMARY KEY,  -- Unix time (s) of the start of the hour
                energy_ws  REAL    NOT NULL,     -- Sum of watts x seconds in this hour
                seconds    INTEGER NOT NULL,     -- Seconds of data in this hour
                peak       REAL    NOT NULL      -- Highest stored power in this hour
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

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
        
        # samples
        conn.execute("""
            CREATE TABLE IF NOT EXISTS samples (
                ts     INTEGER PRIMARY KEY,  -- Unix time (s) of the end of the interval
                power  REAL    NOT NULL,     -- Average watts over the interval
                is_on  INTEGER,              -- Relay state at the end of the interval
                dt     INTEGER NOT NULL      -- Interval length in seconds, used for energy
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(samples)"
            )
        }

        if "create_time" not in columns:
            conn.execute("""
                ALTER TABLE samples
                ADD COLUMN create_time DATETIME
            """)

        if "update_time" not in columns:
            conn.execute("""
                ALTER TABLE samples
                ADD COLUMN update_time DATETIME
            """)

        conn.execute("""
            UPDATE samples
            SET
                create_time = COALESCE(create_time, CURRENT_TIMESTAMP),
                update_time = COALESCE(update_time, CURRENT_TIMESTAMP)
            WHERE create_time IS NULL OR update_time IS NULL
        """)

migrate(DB_PATH)