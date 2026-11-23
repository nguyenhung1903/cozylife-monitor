import sqlite3
from contextlib import asynccontextmanager, closing
import time
import os

# Each range reads from one table and splits the period into buckets.
#   "fixed"  buckets have a constant size in seconds.
#   "day" / "month" buckets follow the local calendar (midnight to midnight, 1st to 1st).
RANGES = {
    "hour":  {"table": "samples", "unit": "fixed", "span": 3600,         "bucket": 60,   "kind": "line"},
    "day":   {"table": "samples", "unit": "fixed", "span": 86400,        "bucket": 600,  "kind": "line"},
    "week":  {"table": "hourly",  "unit": "fixed", "span": 7 * 86400,    "bucket": 3600, "kind": "line"},
    "month": {"table": "hourly",  "unit": "day",   "count": 30, "fmt": "%Y-%m-%d",      "kind": "bar"},
    "year":  {"table": "hourly",  "unit": "month", "count": 12, "fmt": "%Y-%m",         "kind": "bar"},
}

# Per table: (energy in watt-seconds, seconds covered, peak watts)
_COLUMNS = {
    "samples": ("power * dt", "dt", "power"),
    "hourly": ("energy_ws", "seconds", "peak"),
}

RAW_RETENTION_DAYS = int(os.getenv("PLUG_RAW_RETENTION_DAYS", "3"))
# # Hourly summaries are small (about 8,800 rows per year) and are kept for 3 years.
# RETENTION_DAYS = int(os.getenv("PLUG_RETENTION_DAYS", str(3 * 365)))

class DatabaseConnection():
    def __init__(self, db_path):
        self.db_path = db_path
        self.RANGES = RANGES
        self._COLUMNS = _COLUMNS
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


    def save_sample(self, ts: int, power: float, is_on, dt: int) -> None:
        """Store one raw row and fold it into the matching hourly summary, in one transaction."""
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO samples (ts, power, is_on, dt) VALUES (?, ?, ?, ?)",
                (ts, power, None if is_on is None else int(is_on), dt),
            )
            if cur.rowcount:  # Skip the summary if the raw row was a duplicate
                conn.execute(
                    """
                    INSERT INTO hourly (ts, energy_ws, seconds, peak) VALUES (?, ?, ?, ?)
                    ON CONFLICT(ts) DO UPDATE SET
                        energy_ws = energy_ws + excluded.energy_ws,
                        seconds   = seconds + excluded.seconds,
                        peak      = MAX(peak, excluded.peak)
                    """,
                    (ts - ts % 3600, power * dt, dt, power),
                )


    def purge_old(self) -> None:
        now = int(time.time())
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM samples WHERE ts < ?", (now - RAW_RETENTION_DAYS * 86400,))
            # conn.execute("DELETE FROM hourly WHERE ts < ?", (now - RETENTION_DAYS * 86400,))