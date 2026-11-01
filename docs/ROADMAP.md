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
| 7d | NDVI change between two dates | Done. Real run 2026-11-01: overlap 47.7%, 90.1% stable, 9.3% increase, 0.6% decrease |
| 8a-8e | C telemetry packet, Python decoder, C-to-Python cross-check, C health monitor, scripted fault scenario | Done. Laptop only, not flight-qualified |
| 9 | Integration, logging, scheduled ingestion, current TLEs, pass API | Planned |
| 10 | Hardware roadmap | Written: see `HARDWARE_ROADMAP.md` (a proposal, nothing built) |

Also planned: WGS-84 geodetic latitude for ground tracks, UT1-UTC and polar motion,
hardware abstraction layer and command message format for the C code, NDVI time series (7e).