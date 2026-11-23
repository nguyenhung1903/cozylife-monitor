import sqlite3
import threading
import time


class LifecycleService:
    def __init__(self, dbConn, discordBot):
        self.dbConn = dbConn
        self.discordBot = discordBot
        self._lock = threading.Lock()
        self._session_id = None
        
    def start(self):
        with self._lock, self.dbConn._connect() as conn:      
            previous = conn.execute("""
                SELECT create_time
                FROM samples
                ORDER BY create_time DESC
                LIMIT 1;
            """).fetchone()

            previous_time = previous[0] if previous else None
            create_time, update_time = self.dbConn._get_current_time()
            startup_time = create_time
            cursor = conn.execute("""
                INSERT INTO system_lifecycle (
                    shutdown_time,
                    startup_time,
                    create_time,
                    update_time
                )
                VALUES (?, ?, ?, ?)
            """, (previous_time, startup_time, create_time, update_time))
            
            self.discordBot.notify_shutdown_event(shutdown_time=previous_time, startup_time=startup_time)

    def get_history(self, max_history = 10):
        now = time.time()

        with self._lock, self.dbConn._connect() as conn:
            rows = conn.execute("""
                SELECT
                    id,
                    startup_time,
                    shutdown_time,
                    create_time
                FROM system_lifecycle
                ORDER BY create_time DESC
                LIMIT ?
            """, (max_history,)).fetchall()

        return [
            {
                "id": row[0],
                "startup_time": row[1],
                "shutdown_time": row[2],
            }
            for row in rows
        ]
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from database.conn import DatabaseConnection
    dbConn = DatabaseConnection(db_path="database/smartplug-monitor.db")
    LifecycleService(dbConn=dbConn).start()