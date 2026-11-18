import logging
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from services.smartplug import SmartPlug
from dotenv import load_dotenv
load_dotenv()

log = logging.getLogger("smart_plug")

PLUG_IP = os.getenv("SMART_PLUG_IP", "192.168.1.100")
PLUG_PORT = int(os.getenv("SMART_PLUG_PORT", "5555"))
# Raw power value is divided by this before it is shown or stored.
# Set to 10 if the CozyLife app shows a value 10x smaller than the dashboard.
POWER_DIVISOR = float(os.getenv("PLUG_POWER_DIVISOR", "1"))

LIVE_INTERVAL_S = float(os.getenv("PLUG_LIVE_INTERVAL", "2"))    # How often the plug is read
SAVE_INTERVAL_S = int(os.getenv("PLUG_SAVE_INTERVAL", "10"))     # How often an average is stored
RETENTION_DAYS = int(os.getenv("PLUG_RETENTION_DAYS", "30"))     # Older rows are deleted
STALE_AFTER_S = 10                                               # Live reading older than this is "offline"
DB_PATH = Path(os.getenv("PLUG_DB", Path(__file__).parent / "plug.db"))
STATIC_DIR = Path(__file__).parent / "static"

# range name -> (total span in seconds, bucket size in seconds)
RANGES = {
    "hour": (3600, 60),        # last hour, one point per minute
    "day": (86400, 600),       # last 24 hours, one point per 10 minutes
    "week": (7 * 86400, 3600), # last 7 days, one point per hour
}

plug = SmartPlug(PLUG_IP, port=PLUG_PORT)
_lock = threading.Lock()
_latest: dict | None = None  # Most recent reading (or error) from the sampler thread


# ---------------------------------------------------------------- database

def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, timeout=10)


def init_db() -> None:
    with closing(_connect()) as conn, conn:
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


def save_sample(ts: int, power: float, is_on, dt: int) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT OR REPLACE INTO samples (ts, power, is_on, dt) VALUES (?, ?, ?, ?)",
            (ts, power, None if is_on is None else int(is_on), dt),
        )


def purge_old() -> None:
    cutoff = int(time.time()) - RETENTION_DAYS * 86400
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM samples WHERE ts < ?", (cutoff,))


# ----------------------------------------------------------------- sampler

def _sampler(stop: threading.Event) -> None:
    """Background loop: read the plug often, store a 10 s average, keep the latest reading."""
    global _latest
    window: list[float] = []
    last_on = None
    next_save = time.time() + SAVE_INTERVAL_S
    next_purge = 0.0

    while not stop.is_set():
        started = time.time()
        try:
            reading = plug.read()
            power = None if reading.power_w is None else reading.power_w / POWER_DIVISOR
            with _lock:
                _latest = {"is_on": reading.is_on, "power_w": power, "timestamp": started}
            if power is not None:
                window.append(power)
            last_on = reading.is_on
        except (OSError, ValueError) as e:
            with _lock:
                _latest = {"error": str(e), "timestamp": started}

        try:
            now = time.time()
            if now >= next_save:
                if window:
                    save_sample(int(now), sum(window) / len(window), last_on, SAVE_INTERVAL_S)
                window = []
                next_save = now + SAVE_INTERVAL_S
            if now >= next_purge:
                purge_old()
                next_purge = now + 3600
        except sqlite3.Error:
            log.exception("Database error in sampler")

        stop.wait(max(0.0, LIVE_INTERVAL_S - (time.time() - started)))


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    stop = threading.Event()
    thread = threading.Thread(target=_sampler, args=(stop,), daemon=True, name="plug-sampler")
    thread.start()
    yield
    stop.set()
    thread.join(timeout=5)


# --------------------------------------------------------------------- API

app = FastAPI(
    title="Smart Plug API",
    description="Local API for CozyLife Smart Plug monitoring",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"name": "Smart Plug API", "status": "running"}


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    """Serve the dashboard page."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/smart-plug")
def get_plug():
    """Latest relay state and power, as read by the background sampler."""
    with _lock:
        latest = dict(_latest) if _latest else None
    if latest is None:
        raise HTTPException(status_code=503, detail="No reading yet")
    if "error" in latest:
        raise HTTPException(status_code=503, detail=f"Plug unreachable: {latest['error']}")
    if time.time() - latest["timestamp"] > STALE_AFTER_S:
        raise HTTPException(status_code=503, detail="Reading is stale")
    return latest


@app.get("/api/history")
def get_history(range_: Literal["hour", "day", "week"] = Query("hour", alias="range")):
    """Bucketed power history for the last hour, 24 hours or 7 days."""
    span, bucket = RANGES[range_]
    now = int(time.time())
    end = (now // bucket + 1) * bucket  # Next bucket boundary, so the current bucket is included
    start = end - span

    with closing(_connect()) as conn:
        rows = conn.execute(
            """
            SELECT (ts - ?) / ? AS b, AVG(power), MAX(power)
            FROM samples WHERE ts >= ? AND ts < ? GROUP BY b
            """,
            (start, bucket, start, end),
        ).fetchall()
        avg, peak, joules, count = conn.execute(
            "SELECT AVG(power), MAX(power), SUM(power * dt), COUNT(*) FROM samples WHERE ts >= ? AND ts < ?",
            (start, end),
        ).fetchone()

    by_index = {int(b): (a, m) for b, a, m in rows}
    points = []
    for i in range(span // bucket):
        a, m = by_index.get(i, (None, None))
        points.append({
            "t": start + i * bucket,  # Bucket start, Unix seconds
            "avg": None if a is None else round(a, 2),
            "max": None if m is None else round(m, 2),
        })

    return {
        "range": range_,
        "start": start,
        "bucket_s": bucket,
        "save_interval_s": SAVE_INTERVAL_S,
        "points": points,
        "stats": {
            "avg": None if avg is None else round(avg, 2),
            "peak": None if peak is None else round(peak, 2),
            # Watt-seconds -> kWh (estimated by adding up the stored readings)
            "energy_kwh": round((joules or 0) / 3_600_000, 4),
            "samples": count,
        },
    }
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )