import sqlite3
import threading
import time


class SystemLifecycleService:
    def __init__(self, dbConn):
        self.dbConn = dbConn
        self._lock = threading.Lock()
        self._session_id = None
        
    def start(self):
        now = time.time()

        with self._lock, self.dbConn._connect() as conn:

            previous = conn.execute("""
                SELECT shutdown_time
                FROM system_lifecycle
                ORDER BY id DESC
                LIMIT 1
            """).fetchone()

            cursor = conn.execute("""
                INSERT INTO system_lifecycle (
                    shutdown_time
                    startup_time
                )
                VALUES (?, ?)
            """, (now, offline))

            self._session_id = cursor.lastrowid

    def history(self, max_history = 10):
        now = time.time()

        with self._lock, self.dbConn._connect() as conn:
            rows = conn.execute("""
                SELECT
                    id,
                    startup_time,
                    shutdown_time,
                    offline_seconds
                FROM system_lifecycle
                ORDER BY id DESC
                LIMIT ?
            """, (max_history,)).fetchall()

        return [
            {
                "id": row[0],
                "startup_time": row[1],
                "shutdown_time": row[2],
                "offline_seconds": row[3],
                "uptime_seconds": max(
                    0,
                    (row[2] if row[2] is not None else now) - row[1]
                )
            }
            for row in rows
        ]