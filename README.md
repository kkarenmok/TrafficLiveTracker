# TrafficLiveTracker

FastAPI service for showing live London bus arrivals on a Raspberry Pi or any
local display client.

The app uses the Transport for London Unified API and normalizes live bus
arrival predictions into a compact local API.

## Features

- `GET /health` service health check.
- `GET /stops` configured London bus stops.
- `GET /arrivals/{stop_id}` live arrivals for one stop.
- `GET /dashboard` display-ready arrivals for all configured stops.
- Optional route filtering per stop.
- TfL API failures are returned as clear HTTP errors.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

TfL recommends registering for an API key. The app can run without a key for
some public requests, but production use should set one:

```bash
export TFL_APP_KEY="your-tfl-api-key"
```

Optional configuration:

```bash
export STOPS_CONFIG_PATH="config/stops.json"
export REFRESH_SECONDS="30"
export TFL_TIMEOUT_SECONDS="10"
```

Edit `config/stops.json` with your bus stop IDs, display names, and optional
route filters.

## Run Locally

```bash
uvicorn traffic_live_tracker.main:app --host 0.0.0.0 --port 8000
```

Then open:

- `http://localhost:8000/health`
- `http://localhost:8000/stops`
- `http://localhost:8000/dashboard`
- `http://localhost:8000/docs`

## Raspberry Pi Boot Service

Create `/etc/systemd/system/traffic-live-tracker.service`:

```ini
[Unit]
Description=TrafficLiveTracker API
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/home/pi/TrafficLiveTracker
Environment=TFL_APP_KEY=your-tfl-api-key
Environment=STOPS_CONFIG_PATH=config/stops.json
ExecStart=/home/pi/TrafficLiveTracker/.venv/bin/uvicorn traffic_live_tracker.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
User=pi

[Install]
WantedBy=multi-user.target
```

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable traffic-live-tracker
sudo systemctl start traffic-live-tracker
```

## Tests

```bash
pytest
```
