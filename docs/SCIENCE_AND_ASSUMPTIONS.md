# Science and assumptions

## Orbit models

- **Idealized orbit** (`kepler.py`): circular two-body orbit, no drag, no Earth oblateness.
  Period T = 2 pi sqrt(a^3 / mu), speed v = sqrt(mu / a), mu = 398600.4418 km^3/s^2,
  Earth radius 6378.137 km. Starts at the ascending node at t = 0. SIMULATED.
- **SGP4** (`propagate.py`): the standard TLE propagator. Output is in the TEME frame, which we
  treat as the inertial frame. A TLE is only accurate near its epoch.
- **Earth-fixed frame**: rotate about z by GMST (`frames.py`). UT1 is approximated by UTC
  (error under 0.9 s, about 450 m at the equator). Polar motion is ignored.
  The idealized model assumes the frames align at t = 0 and rotates at 7.2921159e-5 rad/s.
- **Latitude for ground tracks is spherical** (geocentric), up to about 0.2 degrees below
  geodetic latitude. Observer positions in `passes.py` use WGS-84.
- **Elevation**: asin of the range vector projected on the local up vector.
  Pass times are accurate to the 30 s step.
- **Visibility footprint**: lambda = acos(R cos(e) / (R + h)) - e on a spherical Earth.
  This is a horizon circle, not a camera swath.
- **Distances** on the ground use the haversine formula (sphere, R = 6371.0088 km).

## Fire alerts

- Severity comes from distance zone (inside AOI, within 30 km, within 100 km) and VIIRS
  confidence (l/n/h). Thresholds live in `config/alert_rules.json`.
- Detections older than 24 hours are ignored. A detection within 1 km of an existing alert
  in the last 12 hours is merged; a more severe one creates a new alert.
- Every alert says "UNCONFIRMED". There is no independent corroboration yet.

## NDVI

- NDVI = (NIR - Red) / (NIR + Red) from surface reflectance:
  reflectance = DN x scale + offset (scale 0.0001, offset -0.1, read from metadata).
- Invalid pixels (no-data, non-finite, negative reflectance, zero denominator, masked by SCL)
  are NaN. We never compute NDVI from RGB images.
- NDVI measures greenness. It is not a direct measure of plant health, yield or drought.
- Valid SCL classes: 4 vegetation, 5 not vegetated, 6 water. All cloud, shadow, thin cirrus,
  saturated, dark, unclassified and no-data pixels are excluded (conservative; thin cirrus
  removed about a third of the AOI in the first scene).
- Reading at 1/4 resolution averages 16 pixels; mixed cloud/clear pixels can leak a little cloud.
- Categories and change thresholds are illustrative and configurable
  (`config/ndvi_categories.json`, `config/ndvi_change.json`). They are not land-cover classes.
- The map overlay is a lat/lon rectangle over a UTM raster: up to roughly 50 m of edge
  offset. Fine for display, not for measurement.
- NDVI change compares only pixels usable on both dates. A change can come from harvest,
  ploughing, flooding, haze or season; the map does not say why.