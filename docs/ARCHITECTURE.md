# Architecture

## Data flow

    Real sources (NASA FIRMS, Sentinel-2 via Earth Search)    Orbit models (SIMULATED)
                 |                                                      |
            ingestion / readers                               propagation, frames, passes
                 |                                                      |
         validation + timestamps                                        |
                 |                                                      |
       fire alerts, NDVI, NDVI change                                   |
                 |                                                      |
             SQLite + cached files  <----------------------------------+
                 |
           FastAPI (JSON, GeoJSON, PNG)
                 |
        React dashboard: Three.js globe, Leaflet map, alerts panel

The orbit simulator is independent of the real-data pipeline. A virtual pass does not
trigger or imply a real observation.

## Backend modules (`backend/app`)

| Module | Purpose |
|---|---|
| `orbit/kepler.py` | Idealized circular orbit: period, speed, inertial position, ground track |
| `orbit/propagate.py` | SGP4 propagation from a TLE (TEME frame) |
| `orbit/frames.py` | GMST and TEME to Earth-fixed rotation |
| `orbit/tle_track.py` | Ground track from a TLE |
| `orbit/passes.py` | Elevation above the AOI centre, pass windows |
| `orbit/footprint.py` | Horizon-limited visibility circle |
| `aoi.py` | Area of interest from `config/aoi_vijayawada.geojson` |
| `ingestion/firms.py`, `run_firms.py` | FIRMS fetch, row validation, storage |
| `ingestion/stac.py` | Sentinel-2 catalogue search (Earth Search) |
| `storage/db.py` | SQLite schema for ingestion runs and fire detections |
| `alerts/` | Rules, engine (dedupe, escalation), simulator, history |
| `analysis/` | NDVI maths, scene reader, categories, NDVI change, caches |
| `fires_api.py`, `alerts_api.py`, `vegetation_api.py`, `change_api.py` | HTTP endpoints |

## HTTP endpoints

| Endpoint | Content |
|---|---|
| `/api/health` | Server status |
| `/api/orbit/ground-track` | SIMULATED idealized orbit track |
| `/api/orbit/tle-ground-track` | SIMULATED SGP4 track from a built-in TEST-FIXTURE TLE (Dec 2019) |
| `/api/orbit/footprint` | Visibility circle radius |
| `/api/aoi` | Configured area of interest (CONFIG) |
| `/api/fires` | Stored FIRMS detections (REAL_EXTERNAL, unconfirmed) |
| `/api/alerts?origin=real\|simulated` | Alert history, kept in separate databases |
| `/api/vegetation/latest` and `.png` | Latest NDVI result |
| `/api/vegetation/change/latest` and `.png` | Latest NDVI change result |

## Storage

- `backend/data/orbital_eye.db` (real): `ingestion_runs`, `fire_detections`, `alerts`,
  `alert_evaluations`, `vegetation_results`, `vegetation_changes`.
- `backend/data/simulation.db`: SIMULATED alerts only, so they can never mix with real data.
- `backend/data/vegetation/`: NDVI and change PNGs and per-scene array caches.
- All of `backend/data/` is ignored by Git.

## Not connected / not built

- No spacecraft telemetry or hardware link.
- Orbit views use a December 2019 test-fixture TLE, not a current one (CelesTrak not yet integrated).
- Pass prediction exists as a function but has no API endpoint or UI yet.
- No scheduled ingestion: data refreshes only when you run the commands in the README.
- C/C++ flight-logic module: not started (Phase 8).