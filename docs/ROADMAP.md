# Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Project foundation, backend and frontend start | Done |
| 2 | Orbit maths, ground-track API, 3D globe, telemetry panel | Done |
| 3 | SGP4, GMST frame conversion, TLE ground-track API | Done (fixture TLE only) |
| 4 | AOI, Leaflet map, pass prediction, visibility footprint | Done (no pass API/UI yet) |
| 5 | NASA FIRMS ingestion, validation, SQLite, map markers | Done |
| 6 | Alert rules, deduplication, history, alerts panel, notifications | Done |
| 7a-7c | Sentinel-2 discovery, NDVI maths, single-date NDVI map | Done |
| 7d | NDVI change between two dates | Code and tests written; end-to-end real-data run to be confirmed |
| 7e | NDVI time series for the AOI | Planned |
| 8 | C/C++ mission-logic module: telemetry structs, sensor interfaces, tests | Planned |
| 9 | Integration, logging, scheduled ingestion, documentation | Planned |
| 10 | Hardware roadmap (sensors, power, onboard computer, ground station) | Planned |

Also planned: current TLEs from CelesTrak (after verifying access terms), WGS-84
geodetic latitude for ground tracks, UT1-UTC and polar motion, pass-prediction API.