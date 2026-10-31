# ORBITAL-EYE

Earth-observation software prototype, initially for Vijayawada, Andhra Pradesh, India.
It simulates an orbit, ingests real fire and vegetation data from public sources, and
shows everything on a dashboard and map.

**There is no satellite hardware connected.** Nothing here is flight software.

## Data labels (used everywhere)

- `REAL_EXTERNAL`: real data from a documented public source (NASA FIRMS, Sentinel-2).
- `SIMULATED`: produced by our own models or test events. Never real observations.
- `SPACECRAFT_TELEMETRY`: reserved for a real spacecraft link. Currently unused.

## Quick start (Windows PowerShell)

Backend (terminal 1):

    cd backend
    .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

Frontend (terminal 2):

    cd frontend
    npm run dev

Open http://localhost:5173. API docs: http://127.0.0.1:8000/docs

## First-time setup

1. Python 3.12 venv in `backend\.venv`, then install: fastapi, uvicorn, sgp4, numpy,
   pytest, httpx, rasterio, pillow.
2. `cd frontend; npm install`.
3. Get a free NASA FIRMS MAP_KEY and store it in `.env` as `FIRMS_MAP_KEY=...`
   (see `.env.example`). Never commit `.env`; never put the key in frontend code.

## Refreshing real data (manual for now)

    cd backend
    .\.venv\Scripts\python.exe -m app.ingestion.run_firms       # fire detections
    .\.venv\Scripts\python.exe -m app.alerts.run_alerts         # evaluate alert rules
    .\.venv\Scripts\python.exe -m app.analysis.vegetation_job   # NDVI for the AOI
    .\.venv\Scripts\python.exe -m app.analysis.change_job       # NDVI change, two dates
    .\.venv\Scripts\python.exe -m app.alerts.simulate           # SIMULATED test alerts

## Tests

    cd backend
    .\.venv\Scripts\python.exe -m pytest -q

## Documents

`docs\ARCHITECTURE.md`, `ROADMAP.md`, `DATA_SOURCES.md`, `SCIENCE_AND_ASSUMPTIONS.md`,
`TESTING.md`.