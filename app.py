import logging
import os
import time
from pathlib import Path
from typing import Literal
from database.conn import DatabaseConnection
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from modules.smartplug import SmartPlug
from services.electronic_sampler import ElectronicSamplerService
from services.monitor_service import MonitorService
from services.lifecycle_service import LifecycleService

from dotenv import load_dotenv
load_dotenv()

log = logging.getLogger("smart_plug")

PLUG_IP = os.getenv("SMART_PLUG_IP", "192.168.1.100")
PLUG_PORT = int(os.getenv("SMART_PLUG_PORT", "5555"))
STALE_AFTER_S = 10                                               # Live reading older than this is "offline"
DB_PATH = os.getenv("PLUG_DB", "plug.db")
STATIC_DIR = Path(__file__).parent / "static"
plug = SmartPlug(PLUG_IP, port=PLUG_PORT)
dbConn = DatabaseConnection(DB_PATH)
elecSampler = ElectronicSamplerService(dbConn=dbConn, plug = plug, log=log)
monitorService = MonitorService(dbConn = dbConn)
lifecycleService = LifecycleService(dbConn=dbConn)

# --------------------------------------------------------------------- API
app = FastAPI(
    title="Smart Plug API",
    description="Local API for CozyLife Smart Plug monitoring",
    version="3.0.0",
    lifespan=elecSampler.lifespan,
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
    latest = elecSampler.latest
    if latest is None:
        raise HTTPException(status_code=503, detail="No reading yet")
    if "error" in latest:
        raise HTTPException(status_code=503, detail=f"Plug unreachable: {latest['error']}")
    if time.time() - latest["timestamp"] > STALE_AFTER_S:
        raise HTTPException(status_code=503, detail="Reading is stale")
    return latest

@app.get("/api/history")
def get_history(range_: Literal["hour", "day", "week", "month", "year"] = Query("hour", alias="range")):
    try:
        return monitorService.get_history(range_=range_)
    except:
        raise HTTPException(status_code=503, detail="Monitor Service cannot get history")
    
@app.get("/api/system/status")
def get_history(max_history = 10):
    try:
        return lifecycleService.get_history(max_history=max_history)
    except:
        raise HTTPException(status_code=503, detail="LifeCycle Service cannot get history")
    

if __name__ == "__main__":
    import uvicorn
    lifecycleService.start()
    
    uvicorn.run("app:app",
        host=os.getenv("APP_HOST"),
        port=int(os.getenv("APP_PORT")),
        reload=True
    )