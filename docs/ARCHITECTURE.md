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

Separately, the flight-logic code (`flight_core`, C) and its Python decoder form a second,
standalone chain that is not yet connected to the dashboard:

    health monitor (C) -> telemetry packet (C encoder) -> bytes -> Python decoder (cross-check)

## Capability status

| Capability | Status |
|---|---|
| Orbit simulation (idealized and SGP4, fixture TLE) | Implemented, SIMULATED |
| Real fire detections (NASA FIRMS) and alert rules | Implemented, REAL_EXTERNAL |
| Real Sentinel-2 NDVI and NDVI change | Implemented, REAL_EXTERNAL |
| Interactive globe, map, alerts panel | Implemented |
| C telemetry packet, CRC-16, validation | Implemented, laptop only |
| C health monitor (modes, faults, watchdog) | Implemented, laptop only, software watchdog |
| Independent Python decoder, C-to-Python cross-checks | Implemented |
| Current TLEs for a real satellite | Not built (fixture TLE from Dec 2019 only) |
| Pass-prediction API and UI | Function exists, no API or UI |
| Scheduled ingestion | Not built (manual commands) |
| Hardware abstraction layer, command message format | Not built |
| Spacecraft telemetry, commanding, onboard processing | Requires hardware, none exists |

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
| `analysis/ndvi.py`, `ndvi_scene.py` | NDVI maths, scene reader and masking |
| `analysis/categories.py`, `vegetation_job.py`, `vegetation_store.py` | NDVI categories, PNG overlay, stored results |
| `analysis/change.py`, `change_job.py`, `change_store.py`, `scene_cache.py` | NDVI change between two dates, array cache |
| `flight_telemetry.py` | Independent Python decoder for the 19-byte telemetry packet |
| `fires_api.py`, `alerts_api.py`, `vegetation_api.py`, `change_api.py` | HTTP endpoints |

## Flight-logic modules (`flight_core`, C99)

| File | Purpose |
|---|---|
| `include/telemetry.h`, `src/telemetry.c` | 19-byte little-endian packet, CRC-16/CCITT-FALSE, range validation |
| `include/health.h`, `src/health.c` | Health monitor: latched SAFE, fault flags with hysteresis, watchdog, packet builder |
| `tests/test_telemetry.c`, `tests/test_health.c` | Standalone C test programs |
| `tools/emit_packets.c`, `tools/emit_scenario.c` | Write encoder output to files for cross-checking in pytest |

Rules the C code follows: no dynamic allocation, no struct-layout dependence (bytes written
individually), explicit units in names and comments, input validation, and compilation with
`-std=c99 -Wall -Wextra -Wpedantic -Werror`.

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

## Known gaps

- Orbit views use a December 2019 test-fixture TLE, not a current one.
- Ground-track latitude is spherical (up to about 0.2 degrees below geodetic).
- No scheduled ingestion; refresh by running the commands in the README.
- Flight logic is not connected to the dashboard and has no hardware abstraction layer.
## Added in Phase 9

| Module | Purpose |
|---|---|
| `ingestion/celestrak.py`, `tle_store.py`, `run_celestrak.py` | Current orbital elements (REAL_EXTERNAL), validated, stored, fetched at most every 12 h |
| `orbit/geodetic.py` | WGS-84 geodetic conversion (replaces spherical latitude for validation) |
| `orbit/validation.py` | Compares SGP4 predictions with real observation times and places |
| `orbit/pass_predictor.py`, `passes_api.py` | Observation opportunities within half a swath of the AOI centre (PROPAGATED_FROM_REAL_TLE) |
| `scheduler.py`, `task_log.py` | Interval-based refresh jobs, lock file, rotating log, task history |
| `system_api.py` | `/api/system/status`: job health, overdue flags, scheduler state, data freshness |

Endpoints added: `/api/passes/next`, `/api/system/status`. Dashboard panels added: next opportunities, system status.
