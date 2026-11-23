import os
import sqlite3
from contextlib import asynccontextmanager, closing
from dotenv import load_dotenv
load_dotenv()

DB_PATH = os.getenv("PLUG_DB", "plug.db")

class MigrationCreateDatabase():
    def __init__(self, db_path):
        self.db_path = db_path
        
    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)
    
    def run(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("PRAGMA journal_mode=WAL")  # Readers do not block the writer
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS samples (
                    ts     INTEGER PRIMARY KEY,  -- Unix time (s) of the end of the interval
                    power  REAL    NOT NULL,     -- Average watts over the interval
                    is_on  INTEGER,              -- Relay state at the end of the interval
                    dt     INTEGER NOT NULL      -- Interval length in seconds, used for energy
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hourly (
                    ts         INTEGER PRIMARY KEY,  -- Unix time (s) of the start of the hour
                    energy_ws  REAL    NOT NULL,     -- Sum of watts x seconds in this hour
                    seconds    INTEGER NOT NULL,     -- Seconds of data in this hour
                    peak       REAL    NOT NULL      -- Highest stored power in this hour
                )
                """
            )
            # conn.execute(
            #     """
            #     CREATE TABLE IF NOT EXISTS system_lifecycle (
            #             id INTEGER PRIMARY KEY AUTOINCREMENT,
            #             shutdown_time REAL NOT NULL,
            #             startup_time REAL NOT NULL,
            #             create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            #             update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            #     )
            #     """
            # )

if __name__ == "__main__":
    MigrationCreateDatabase(db_path=DB_PATH).run()