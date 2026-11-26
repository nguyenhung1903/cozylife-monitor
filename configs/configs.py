import os
from utils.general import dict_to_namespace
from dotenv import load_dotenv
load_dotenv()

envParams = {
    "ENV": os.getenv("ENV"), # production / dev
    "APP":{
        "HOST": os.getenv("APP_HOST"),
        "PORT": int(os.getenv("APP_PORT")),
        "STATIC_DIR": os.getenv("APP_STATIC_DIR")
    },
    
    "SMART_PLUG_DEVICE": {
        "IP": os.getenv("SMART_PLUG_IP", "192.168.1.100"),
        "PORT": int(os.getenv("SMART_PLUG_PORT", "5555")),
        
    },
    
    "SAMPLER": {
        "STALE_AFTER_S": int(os.getenv("PLUG_STALE_AFTER_S", "10")),
        "POWER_DIVISOR": float(os.getenv("PLUG_POWER_DIVISOR", "1")), # Set to 10 if the CozyLife app shows a value 10x smaller than the dashboard.
        "LIVE_INTERVAL_S": float(os.getenv("SMART_PLUG_COLLECTION_TIME", "5")),    # How often the plug is read
        "SAVE_INTERVAL_S": int(os.getenv("PLUG_SAVE_INTERVAL", "10")),
    },
    
    "DATABASE": {
        "DB_PATH": os.getenv("PLUG_DB", "plug.db"),
        "RAW_RETENTION_DAYS": int(os.getenv("PLUG_RAW_RETENTION_DAYS", "3")),
        "RETENTION_DAYS": int(os.getenv("PLUG_RETENTION_DAYS", str(3 * 365)))  # Hourly summaries are small (about 8,800 rows per year) and are kept for 3 years.
    },
    
    "DISCORD":{
        "BOT": {
            "TOKEN": os.getenv("DISCORD_BOT_TOKEN"),
            "CHANNEL_ID": int(os.getenv("DISCORD_BOT_CHANNEL_ID")),
        }
    }
}

envParams = dict_to_namespace(envParams)
