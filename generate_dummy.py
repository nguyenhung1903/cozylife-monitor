
import sqlite3
import random
import time
from datetime import datetime, timezone

DB_PATH = "database/smartplug-monitor_dummy.db"

DAYS = 30
SAMPLE_INTERVAL = 60  # seconds

random.seed(42)


def generate_power(ts):
    """Simulate realistic smart plug power consumption."""
    hour = datetime.fromtimestamp(ts).hour

    # Simulate daily usage patterns
    if 0 <= hour < 6:
        return random.uniform(0, 5)

    if 6 <= hour < 9:
        return random.uniform(30, 150)

    if 9 <= hour < 17:
        return random.uniform(5, 80)

    if 17 <= hour < 23:
        return random.uniform(50, 250)

    return random.uniform(0, 10)


def generate_dummy_data():
    now = int(time.time())
    start = now - DAYS * 86400

    samples = []

    for ts in range(
        start,
        now,
        SAMPLE_INTERVAL
    ):
        power = round(generate_power(ts), 2)

        # Simulate occasional OFF state
        is_on = 0 if random.random() < 0.05 else 1

        if not is_on:
            power = 0.0

        samples.append((
            ts,
            power,
            is_on,
            SAMPLE_INTERVAL
        ))

    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany("""
            INSERT OR IGNORE INTO samples (
                ts, power, is_on, dt
            )
            VALUES (?, ?, ?, ?)
        """, samples)

        # Aggregate samples into hourly records
        conn.execute("""
            INSERT OR IGNORE INTO hourly (
                ts, energy_ws, seconds, peak
            )
            SELECT
                (ts / 3600) * 3600 AS hour_ts,
                SUM(power * dt) AS energy_ws,
                SUM(dt) AS seconds,
                MAX(power) AS peak
            FROM samples
            GROUP BY hour_ts
        """)

    print(f"Generated {len(samples)} samples.")
    print(f"Period: {start} -> {now}")


if __name__ == "__main__":
    generate_dummy_data()
