import logging
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager, closing
from datetime import datetime, timedelta
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
# Hourly summaries are small (about 8,800 rows per year) and are kept for 3 years.
RETENTION_DAYS = int(os.getenv("PLUG_RETENTION_DAYS", str(3 * 365)))
# Raw 10-second rows are only needed for the hour and day views, so they are kept briefly.
RAW_RETENTION_DAYS = int(os.getenv("PLUG_RAW_RETENTION_DAYS", "3"))
STALE_AFTER_S = 10                                               # Live reading older than this is "offline"
DB_PATH = Path(os.getenv("PLUG_DB", Path(__file__).parent / "plug.db"))
STATIC_DIR = Path(__file__).parent / "static"

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
        # One-time migration: build hourly summaries from raw rows saved by an older version
        if conn.execute("SELECT COUNT(*) FROM hourly").fetchone()[0] == 0:
            conn.execute(
                """
                INSERT INTO hourly (ts, energy_ws, seconds, peak)
                SELECT ts - ts % 3600, SUM(power * dt), SUM(dt), MAX(power)
                FROM samples GROUP BY ts - ts % 3600
                """
            )


def save_sample(ts: int, power: float, is_on, dt: int) -> None:
    """Store one raw row and fold it into the matching hourly summary, in one transaction."""
    with closing(_connect()) as conn, conn:
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


def purge_old() -> None:
    now = int(time.time())
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM samples WHERE ts < ?", (now - RAW_RETENTION_DAYS * 86400,))
        conn.execute("DELETE FROM hourly WHERE ts < ?", (now - RETENTION_DAYS * 86400,))


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
    version="3.0.0",
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


def _fixed_buckets(span: int, bucket: int) -> list[tuple[int, int, int]]:
    """Equal-size buckets ending at the next bucket boundary: (from_ts, to_ts, index)."""
    end = (int(time.time()) // bucket + 1) * bucket  # Includes the current, partial bucket
    start = end - span
    return [(start + i * bucket, start + (i + 1) * bucket, i) for i in range(span // bucket)]


def _calendar_buckets(unit: str, count: int, fmt: str) -> list[tuple[int, int, str]]:
    """Local-calendar buckets (days or months) ending with the current one: (from_ts, to_ts, key)."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if unit == "day":
        firsts = [today - timedelta(days=i) for i in range(count - 1, -1, -1)]
        following = lambda d: d + timedelta(days=1)
    else:
        firsts, y, m = [], today.year, today.month
        for _ in range(count):
            firsts.append(datetime(y, m, 1))
            y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        firsts.reverse()
        following = lambda d: datetime(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return [(int(d.timestamp()), int(following(d).timestamp()), d.strftime(fmt)) for d in firsts]


@app.get("/api/history")
def get_history(range_: Literal["hour", "day", "week", "month", "year"] = Query("hour", alias="range")):
    """Bucketed power history: last hour, 24 hours, 7 days, 30 days or 12 months."""
    cfg = RANGES[range_]
    if cfg["unit"] == "fixed":
        buckets = _fixed_buckets(cfg["span"], cfg["bucket"])
        key_sql, key_params = "(ts - ?) / ?", (buckets[0][0], cfg["bucket"])
    else:
        buckets = _calendar_buckets(cfg["unit"], cfg["count"], cfg["fmt"])
        # 'localtime' makes SQLite group by the server's local day or month
        key_sql, key_params = "strftime(?, ts, 'unixepoch', 'localtime')", (cfg["fmt"],)
    start, end = buckets[0][0], buckets[-1][1]

    table = cfg["table"]
    energy, seconds, peak = _COLUMNS[table]
    # table and column names come from the constants above, never from the request
    sql = f"""
        SELECT {key_sql}, SUM({energy}), SUM({seconds}), MAX({peak})
        FROM {table} WHERE ts >= ? AND ts < ? GROUP BY 1
    """
    with closing(_connect()) as conn:
        rows = conn.execute(sql, (*key_params, start, end)).fetchall()
    by_key = {k: (e, s, p) for k, e, s, p in rows}

    points = []
    total_ws = total_s = 0.0
    top = None
    for frm, to, key in buckets:
        e, s, p = by_key.get(key, (None, None, None))
        if s:
            total_ws += e
            total_s += s
            top = p if top is None else max(top, p)
        points.append({
            "from": frm,  # Bucket start, Unix seconds
            "to": to,     # Bucket end (exclusive)
            "avg": round(e / s, 2) if s else None,
            "max": round(p, 2) if s else None,
            "kwh": round(e / 3_600_000, 4) if s else None,
        })

    return {
        "range": range_,
        "kind": cfg["kind"],  # "line" plots average watts, "bar" plots kWh per bucket
        "save_interval_s": SAVE_INTERVAL_S,
        "points": points,
        "stats": {
            "avg": round(total_ws / total_s, 2) if total_s else None,
            "peak": round(top, 2) if top is not None else None,
            # Watt-seconds -> kWh (estimated by adding up the stored readings)
            "energy_kwh": round(total_ws / 3_600_000, 4),
            "has_data": total_s > 0,
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