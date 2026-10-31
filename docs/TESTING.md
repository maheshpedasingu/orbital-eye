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