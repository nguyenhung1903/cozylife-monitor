import os
import sqlite3
import time
import threading
from contextlib import asynccontextmanager, closing
from fastapi import FastAPI
from configs import envParams

class ElectronicSamplerService:

    def __init__(
        self,
        dbConn,
        plug,
        log
    ):
        self.dbConn = dbConn
        self.plug = plug
        self.log = log
        
        self._lock = threading.Lock()
        self._latest = None
        self._stop = None
        self._thread = None

    @property
    def latest(self):
        with self._lock:
            return dict(self._latest) if self._latest else None

    def _sampler(self, stop: threading.Event):
        window = []
        last_on = None
        next_save = time.time() + envParams.SAMPLER.SAVE_INTERVAL_S
        next_purge = 0.0

        while not stop.is_set():
            started = time.time()

            try:
                reading = self.plug.read()

                power = (
                    None if reading.power_w is None
                    else reading.power_w / envParams.SAMPLER.POWER_DIVISOR
                )

                with self._lock:
                    self._latest = {
                        "is_on": reading.is_on,
                        "power_w": power,
                        "timestamp": started
                    }

                if power is not None:
                    window.append(power)

                last_on = reading.is_on

            except (OSError, ValueError) as e:
                with self._lock:
                    self._latest = {
                        "error": str(e),
                        "timestamp": started
                    }

            try:
                now = time.time()

                if now >= next_save:
                    if window:
                        self.dbConn.save_sample(
                            int(now),
                            sum(window) / len(window),
                            last_on,
                            envParams.SAMPLER.SAVE_INTERVAL_S
                        )

                    window = []
                    next_save = now + envParams.SAMPLER.SAVE_INTERVAL_S

                if now >= next_purge:
                    self.dbConn.purge_old()
                    next_purge = now + 3600

            except sqlite3.Error:
                self.log.exception("Database error in sampler")

            stop.wait(max(0.0, envParams.SAMPLER.LIVE_INTERVAL_S - (time.time() - started)))

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        self.dbConn.init_db()

        self._stop = threading.Event()

        self._thread = threading.Thread(
            target=self._sampler,
            args=(self._stop,),
            daemon=True,
            name="plug-sampler"
        )

        self._thread.start()

        self.log.info("Smart plug sampler started")

        try:
            yield
        finally:
            self._stop.set()
            self._thread.join(timeout=5)

            self.log.info("Smart plug sampler stopped")
