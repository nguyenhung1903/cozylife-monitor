import sqlite3
from contextlib import asynccontextmanager, closing
import time
import os
import datetime
from configs import envParams

class DatabaseConnection():
    def __init__(self, db_path):
        self.db_path = db_path
        print("LOAD: ", self.db_path)
        
    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)

    def init_db(self) -> None:
        with closing(self._connect()) as conn, conn:
            # One-time migration: build hourly summaries from raw rows saved by an older version
            if conn.execute("SELECT COUNT(*) FROM hourly").fetchone()[0] == 0:
                conn.execute(
                    """
                    INSERT INTO hourly (ts, energy_ws, seconds, peak)
                    SELECT ts - ts % 3600, SUM(power * dt), SUM(dt), MAX(power)
                    FROM samples GROUP BY ts - ts % 3600
                    """
                )


    def _get_current_time(self):
        tz_vn = datetime.timezone(datetime.timedelta(hours=7))
        now = datetime.datetime.now(tz_vn)
        create_time = now.isoformat(timespec="seconds")
        update_time = now.isoformat(timespec="seconds")
        
        return create_time, update_time
    
    def save_sample(self, ts: int, power: float, is_on, dt: int) -> None:
        """Store one raw row and fold it into the matching hourly summary, in one transaction."""
        
        create_time, update_time = self._get_current_time()
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO samples (ts, power, is_on, dt, create_time, update_time) VALUES (?, ?, ?, ?, ?, ?)",
                (ts, power, None if is_on is None else int(is_on), dt, create_time, update_time),
            )
            if cur.rowcount:  # Skip the summary if the raw row was a duplicate
                create_time, update_time = self._get_current_time()
                conn.execute(
                    """
                    INSERT INTO hourly (ts, energy_ws, seconds, peak, create_time, update_time) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ts) DO UPDATE SET
                        energy_ws = energy_ws + excluded.energy_ws,
                        seconds   = seconds + excluded.seconds,
                        peak      = MAX(peak, excluded.peak)
                    """,
                    (ts - ts % 3600, power * dt, dt, power, create_time, update_time),
                )


    def purge_old(self) -> None:
        now = int(time.time())
        DAY_TOTAL_SECONDS = 86400
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM samples WHERE ts < ?", (now - envParams.DATABASE.RAW_RETENTION_DAYS * DAY_TOTAL_SECONDS,))
            # conn.execute("DELETE FROM hourly WHERE ts < ?", (now - envParams.DATABASE.RETENTION_DAYS * DAY_TOTAL_SECONDS,))