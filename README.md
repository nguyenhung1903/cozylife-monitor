# CozyLife Monitor

### An IoT-based Electronic Monitoring System

A lightweight monitoring platform built with Python and FastAPI to track electrical power consumption and system availability using a CozyLife Wi-Fi Smart Plug.

The system collects real-time power readings, maintains historical consumption records, provides a web-based dashboard, and detects system shutdown and restart events with Discord notifications.

---

## Features

### 1. Smart Plug Monitoring

- Connects to a CozyLife Wi-Fi Smart Plug through its local TCP interface.
- Retrieves device relay status (ON/OFF).
- Collects instantaneous power consumption (Watts).
- Continuously samples power readings in the background.
- Supports configurable sampling and storage intervals.

### 2. Power Consumption Analytics

- Stores power consumption samples in SQLite.
- Aggregates historical measurements into hourly summaries.
- Calculates average and peak power consumption.
- Estimates energy consumption in kWh.
- Provides historical data across multiple time ranges:
  - Last hour
  - Last 24 hours
  - Last 7 days
  - Last 30 days
  - Last 12 months

### 3. System Lifecycle Monitoring

- Detects system startup and records the previous shutdown time.
- Maintains system lifecycle history.
- Calculates system downtime.
- Sends Discord notifications when the system restarts.

### 4. Web Dashboard

- Real-time power monitoring.
- Current device operating status.
- Minimum, average, and maximum power statistics.
- Interactive historical power consumption charts.
- System shutdown and restart history.
- Responsive interface with light and dark theme support.

---

## Architecture

```text
                 CozyLife Wi-Fi Smart Plug
                            |
                       Local TCP
                            |
                            v
                    SmartPlug Module
                            |
                            v
                 ElectronicSamplerService
                            |
                 +----------+----------+
                 |                     |
                 v                     v
           SQLite Database       Live Readings
                 |                     |
                 v                     v
             MonitorService       FastAPI Server
                 |                     |
                 +----------+----------+
                            |
                            v
                       Web Dashboard


                 System Lifecycle Service
                            |
                    SQLite Database
                            |
                            v
                    Discord Bot Service
                            |
                            v
                   Discord Notifications
```

---

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python 3.12 |
| Web Framework | FastAPI |
| ASGI Server | Uvicorn |
| Database | SQLite |
| Smart Plug Communication | TCP / JSON |
| Discord Notifications | discord.py |
| Frontend | HTML, CSS, JavaScript |
| Containerization | Docker |
| Configuration | Python Dotenv |

---

## Project Structure

```text
cozylife-monitor/
├── database/
│   └── ...
├── migrations/
│   └── ...
├── modules/
│   └── smartplug.py
├── services/
│   ├── electronic_sampler.py
│   ├── monitor_service.py
│   ├── lifecycle_service.py
│   └── discordbot_service.py
├── static/
│   └── index.html
├── .env.example
├── app.py
├── deploy.sh
├── dockerfile
├── requirements.txt
└── README.md
```

---

## Requirements

- Python 3.12+
- CozyLife Wi-Fi Smart Plug with power monitoring support.
- Smart Plug and monitoring server connected to the same local network.
- Discord Bot Token and a Discord channel ID (for notifications).
- Docker (optional).

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/nguyenhung1903/cozylife-monitor.git

cd cozylife-monitor
```

### 2. Install dependencies

```bash
python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Configure the following parameters:

```env
APP_HOST=0.0.0.0
APP_PORT=8000

SMART_PLUG_IP=192.168.1.100
SMART_PLUG_PORT=5555
SMART_PLUG_POWER_DIVISOR=1

PLUG_DB=database/smartplug-monitor.db

DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_BOT_CHANNEL_ID=your_discord_channel_id
```

Make sure the Smart Plug IP address is correct and accessible from the monitoring server.

The Discord Bot must have permission to view the target channel and send messages.

### 4. Initialize Database

```bash
python migrations/init_migration.py
```

### 5. Run the application

```bash
python app.py
```

The dashboard will be available at:

```text
http://localhost:8000/dashboard
```

---

## Docker Deployment

Build and deploy the application using the provided deployment script:

```bash
chmod +x deploy.sh

./deploy.sh
```

The deployment script:

1. Builds the Docker image.
2. Removes the previous container.
3. Starts a new container.
4. Mounts the database directory for persistent storage.
5. Configures automatic container restart.

The application will be accessible at:

```text
http://localhost:8000/dashboard
```

To inspect application logs:

```bash
docker logs -f cozylife-monitor
```

To stop the container:

```bash
docker stop cozylife-monitor
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Application status |
| GET | `/dashboard` | Monitoring dashboard |
| GET | `/api/smart-plug` | Latest Smart Plug reading |
| GET | `/api/history` | Historical power consumption |
| GET | `/api/system/status` | System lifecycle history |

### Historical Data

The `/api/history` endpoint supports the following query parameters:

```http
GET /api/history?range=hour
GET /api/history?range=day
GET /api/history?range=week
GET /api/history?range=month
GET /api/history?range=year
```

### System Lifecycle

```http
GET /api/system/status?max_history=10
```

Returns the latest system startup and shutdown records.

---

## Discord Notifications

The system uses a Discord Bot to report system lifecycle events.

Example notification:

```text
SYSTEM STATUS

The system went down
06:17:47 AM, and restarted at
06:18:03 AM.

Date: Nov 24, 2026
Duration: 16 s
```

This allows the system administrator to track unexpected downtime and subsequent recovery remotely.

---

## Database

SQLite is used for persistent storage.

The database maintains:

- Raw power consumption samples.
- Hourly aggregated energy statistics.
- System shutdown and startup timestamps.
- Record creation and update timestamps.

Raw measurement records are periodically cleaned up according to the configured retention period, while hourly summaries provide longer-term historical analytics.

---

## References

- [CozyLife Local](https://github.com/soulripper13/cozylife_local)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [discord.py Documentation](https://discordpy.readthedocs.io/)

---

## License

This project is developed for personal use and experimentation.