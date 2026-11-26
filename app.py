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
from services.discordbot_service import DiscordBotService
from configs import envParams, verParams

log = logging.getLogger("smart_plug")

plug = SmartPlug(ip = envParams.SMART_PLUG_DEVICE.IP, port=envParams.SMART_PLUG_DEVICE.PORT)
dbConn = DatabaseConnection(db_path= envParams.DATABASE.DB_PATH)
discordBot = DiscordBotService(token=envParams.DISCORD.BOT.TOKEN,channel_id=envParams.DISCORD.BOT.CHANNEL_ID,logger=log)
elecSampler = ElectronicSamplerService(dbConn=dbConn, plug = plug, log=log)
monitorService = MonitorService(dbConn = dbConn)
lifecycleService = LifecycleService(dbConn=dbConn, discordBot=discordBot)

# --------------------------------------------------------------------- API
app = FastAPI(
    title=verParams.TITLE,
    description=verParams.DESCRIPTION,
    version=verParams.VERSION,
    lifespan=elecSampler.lifespan,
)

@app.get("/")
def root():
    return {"name": "Smart Plug API", "status": "running"}

@app.get("/dashboard", include_in_schema=False)
def dashboard():
    """Serve the dashboard page."""
    return FileResponse(os.path.join(envParams.APP.STATIC_DIR, "index.html"))

@app.get("/api/smart-plug")
def get_plug():
    latest = elecSampler.latest
    if latest is None:
        raise HTTPException(status_code=503, detail="No reading yet")
    if "error" in latest:
        raise HTTPException(status_code=503, detail=f"Plug unreachable: {latest['error']}")
    if time.time() - latest["timestamp"] > envParams.SAMPLER.STALE_AFTER_S:
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
        host=envParams.APP.HOST,
        port=envParams.APP.PORT,
        reload=True
    )