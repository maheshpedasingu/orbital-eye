# Testing

Run everything:

    cd backend
    .\.venv\Scripts\python.exe -m pytest -q

## Tests that check against independent references

- GMST against the worked example in Vallado, Fundamentals of Astrodynamics (Example 3-5).
- Orbital period at geostationary altitude equals one sidereal day (about 86164 s).
- Speed times period equals the orbit circumference.
- One degree of longitude on the equator is about 111.195 km (haversine).
- Footprint radius is zero when the satellite must be directly overhead.
- A satellite placed straight above the observer has 90 degrees elevation; one on the far
  side of Earth is below the horizon.
- Ground-track latitude never exceeds 180 minus inclination.
- NDVI known values, zero denominators (no warnings), masks, range limits.

## Tests that protect the data rules

- Failed or empty fetches are recorded as such and store nothing.
- API keys are redacted from error messages.
- SIMULATED alerts live in a separate database, carry a SIMULATED label, and say UNCONFIRMED.
- Parser tests use invented rows and are marked as fixtures; they are never inserted by the app.
- Duplicate detections are ignored; each detection is evaluated once.

## Not covered by automated tests

- Live calls to NASA FIRMS and Earth Search (verified manually with real runs).
- The React components and Three.js / Leaflet rendering (verified by eye).
- Browser notifications (verified manually).

## Manual checks

1. Compare the NDVI overlay with the street map: the river and built-up centre of
   Vijayawada should fall in the lowest NDVI category.
2. Run `python -m app.alerts.simulate` and tick "Show simulated test events"; expect one
   CRITICAL alert with a merged repeat and one INFO alert, both badged SIMULATED.
3. Run `python -m app.ingestion.run_firms` twice; the second run should add 0 new rows.
## Flight-logic tests (C)

Build and run each test program from the project root:

    gcc -std=c99 -Wall -Wextra -Wpedantic -Werror -Iflight_core/include flight_core/src/telemetry.c flight_core/tests/test_telemetry.c -o flight_core/test_telemetry.exe
    .\flight_core\test_telemetry.exe
    gcc -std=c99 -Wall -Wextra -Wpedantic -Werror -Iflight_core/include flight_core/src/telemetry.c flight_core/src/health.c flight_core/tests/test_health.c -o flight_core/test_health.exe
    .\flight_core\test_health.exe

Each prints `N checks, M failed` and exits 0 only if nothing failed. The telemetry program
printed `41 checks, 0 failed` when last confirmed.

What they check: the CRC against the published check value (`123456789` gives `0x29B1`);
packet bytes against a hand-computed byte sequence; round trips including negative
temperature and range limits; detection of every single-bit corruption; rejection of wrong
lengths, null pointers and out-of-range fields (including a packet with a valid CRC but an
invalid field); health thresholds at exactly the limit and one step beyond; hysteresis
bands; latched SAFE; command acceptance and rejection; watchdog timeout and 32-bit counter
wrap-around.

## C-to-Python cross-checks (pytest, skipped if gcc is not on PATH)

- `test_c_cross_check.py`: the real C encoder writes four packets (typical, minimum, maximum,
  negative temperature); the independently written Python decoder must read every field.
- `test_health_scenario.py`: the C health monitor runs an 11-step scenario; the Python decoder
  checks mode and faults at each step against a table written by hand, not taken from C output.

A skipped test is not a pass: check that the pytest summary shows no skips.

## Limits of this testing

The C code is tested on a Windows laptop with GCC only. Nothing has been run on a target
processor, under a real-time OS, with a hardware watchdog, or in a radiation environment.

Last confirmed full run: 106 passed, no skips (2026-11-01).

HAL tests: build `test_monitor.c` with `telemetry.c health.c hal.c hal_sim.c monitor.c` (same gcc flags) and run it.
`test_hal_scenario.py` requires the HAL-driven scenario to be byte-identical to the direct scenario.

HAL tests: build `test_monitor.c` with `telemetry.c health.c hal.c hal_sim.c monitor.c` (same gcc flags) and run it.
`test_hal_scenario.py` requires the HAL-driven scenario to be byte-identical to the direct scenario.
