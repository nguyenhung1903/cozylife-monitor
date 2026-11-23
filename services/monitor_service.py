import time
from datetime import datetime, timedelta
from typing import Literal
from contextlib import closing
from fastapi import Query
from services.electronic_sampler import SAVE_INTERVAL_S

class MonitorService():
    def __init__(self, dbConn):
        self.dbConn = dbConn

    def _fixed_buckets(self, span: int, bucket: int) -> list[tuple[int, int, int]]:
        """Equal-size buckets ending at the next bucket boundary: (from_ts, to_ts, index)."""
        end = (int(time.time()) // bucket + 1) * bucket  # Includes the current, partial bucket
        start = end - span
        return [(start + i * bucket, start + (i + 1) * bucket, i) for i in range(span // bucket)]


    def _calendar_buckets(self, unit: str, count: int, fmt: str) -> list[tuple[int, int, str]]:
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


    def get_history(self, range_: Literal["hour", "day", "week", "month", "year"] = Query("hour", alias="range")):
        """Bucketed power history: last hour, 24 hours, 7 days, 30 days or 12 months."""
        cfg = self.dbConn.RANGES[range_]
        if cfg["unit"] == "fixed":
            buckets = self._fixed_buckets(cfg["span"], cfg["bucket"])
            key_sql, key_params = "(ts - ?) / ?", (buckets[0][0], cfg["bucket"])
        else:
            buckets = self._calendar_buckets(cfg["unit"], cfg["count"], cfg["fmt"])
            # 'localtime' makes SQLite group by the server's local day or month
            key_sql, key_params = "strftime(?, ts, 'unixepoch', 'localtime')", (cfg["fmt"],)
        start, end = buckets[0][0], buckets[-1][1]

        table = cfg["table"]
        energy, seconds, peak = self.dbConn._COLUMNS[table]
        # table and column names come from the constants above, never from the request
        sql = f"""
            SELECT {key_sql}, SUM({energy}), SUM({seconds}), MAX({peak})
            FROM {table} WHERE ts >= ? AND ts < ? GROUP BY 1
        """
        with closing(self.dbConn._connect()) as conn:
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