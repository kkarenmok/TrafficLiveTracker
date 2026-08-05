# TrafficLiveTracker

A minimal live London bus dashboard. The browser interface is hosted on GitHub
Pages, while a small FastAPI service on Render proxies Transport for London
(TfL) data and stores a shared list of bus stops in PostgreSQL.

Stops R and Q at Mare Street / Victoria Park Road are created when the database
is first provisioned. Any visitor can search for individual bus stops, add them,
remove them, and undo a removal. Changes are shared by every visitor.

## Architecture

- `web/` contains the dependency-free GitHub Pages application.
- `src/traffic_live_tracker/` contains the FastAPI service and TfL client.
- `migrations/` contains the PostgreSQL/SQLite schema and initial stop seed.
- `render.yaml` provisions the Render API and PostgreSQL database.
- `.github/workflows/pages.yml` tests the project and deploys GitHub Pages.

The Pages bundle contains only the public API URL. TfL and database credentials
remain in Render environment variables.

## Local development

Create an environment and install the project:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Initialize the local SQLite database and run the API:

```bash
alembic upgrade head
uvicorn traffic_live_tracker.main:app --reload --port 8000
```

Serve the static site from another terminal:

```bash
python -m http.server 8080 --directory web
```

Open `http://localhost:8080`. The committed local `web/config.js` targets the
API at `http://localhost:8000`.

Optional API settings:

```bash
export TFL_APP_KEY="your-tfl-api-key"
export DATABASE_URL="sqlite:///traffic_live_tracker.db"
export CORS_ORIGINS="http://localhost:8080,https://kkarenmok.github.io"
export REFRESH_SECONDS="30"
export TFL_TIMEOUT_SECONDS="10"
```

## Deploy the API to Render

1. In Render, create a new Blueprint from this GitHub repository. Render reads
   `render.yaml` and creates `traffic-live-tracker-api` plus its PostgreSQL
   database.
2. Enter `TFL_APP_KEY` when prompted. TfL permits some calls without a key, but
   a registered key is recommended for a deployed service.
3. Wait for the service to become healthy at `/health`. The start command runs
   `alembic upgrade head` before Uvicorn, so the first deploy creates and seeds
   the database.
4. Copy the service's HTTPS URL, such as
   `https://traffic-live-tracker-api.onrender.com`.

The Blueprint starts on Render's free tiers. A free web service spins down while
idle, so the first request after inactivity can take about a minute. A free
Render Postgres database expires after 30 days and has no backups; upgrade the
database to `basic-256mb` or another paid tier before relying on it for lasting
shared configuration.

## Deploy the frontend to GitHub Pages

1. In the GitHub repository, open **Settings → Secrets and variables → Actions →
   Variables** and create `API_BASE_URL` with the Render HTTPS URL (without a
   trailing slash).
2. Open **Settings → Pages** and choose **GitHub Actions** as the source.
3. Run the **Test and deploy Pages** workflow, or push to `main`.
4. Open `https://kkarenmok.github.io/TrafficLiveTracker/`.

The workflow refuses to deploy when `API_BASE_URL` is missing and generates the
production `config.js` only inside the Pages artifact.

## API

- `GET /health` — service health.
- `GET /stops` — shared configured stops.
- `GET /stops/search?q=mare%20street` — TfL-ranked individual bus stops.
- `POST /stops` with `{ "id": "490003314R" }` — validate and add a stop.
- `DELETE /stops/{stop_id}` — remove and return a stop.
- `GET /arrivals/{stop_id}` — arrivals for a configured stop.
- `GET /dashboard` — refresh interval and arrivals for all configured stops.
- `GET /docs` — interactive OpenAPI documentation.

Stop editing is intentionally public. Mutation endpoints are transaction-safe,
reject duplicates, and apply a basic per-client rate limit, but authentication
should be added before using the shared list for a sensitive installation.

## Tests

```bash
pytest -q
node --check web/app.js
```
