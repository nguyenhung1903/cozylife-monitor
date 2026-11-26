import os
from utils.general import dict_to_namespace

schemaParams = {
    # Each range reads from one table and splits the period into buckets.
    #   "fixed"  buckets have a constant size in seconds.
    #   "day" / "month" buckets follow the local calendar (midnight to midnight, 1st to 1st).
    "RANGES": {
        "hour":  {"table": "samples", "unit": "fixed", "span": 3600,         "bucket": 60,   "kind": "line"},
        "day":   {"table": "samples", "unit": "fixed", "span": 86400,        "bucket": 600,  "kind": "line"},
        "week":  {"table": "hourly",  "unit": "fixed", "span": 7 * 86400,    "bucket": 3600, "kind": "line"},
        "month": {"table": "hourly",  "unit": "day",   "count": 30, "fmt": "%Y-%m-%d",      "kind": "bar"},
        "year":  {"table": "hourly",  "unit": "month", "count": 12, "fmt": "%Y-%m",         "kind": "bar"},
    },

    # Per table: (energy in watt-seconds, seconds covered, peak watts)
    "COLUMNS":{
        "samples": ("power * dt", "dt", "power"),
        "hourly": ("energy_ws", "seconds", "peak"),
    }
}

schemaParams
