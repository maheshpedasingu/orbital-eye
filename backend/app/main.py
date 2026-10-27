from datetime import datetime, timezone

from fastapi import FastAPI, Query

from app.orbit.kepler import circular_speed_km_s, ground_track, orbital_period_s
from app.orbit.tle_track import tle_ground_track

app = FastAPI(title="ORBITAL-EYE API", version="0.1.0")

# Test fixture from the python-sgp4 docs. Epoch Dec 2019: NOT a current orbit.
FIXTURE_LINE1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
FIXTURE_LINE2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"
FIXTURE_START = datetime(2019, 12, 9, 12, 0, 0, tzinfo=timezone.utc)


@app.get("/api/health")
def health():
    """Basic health check. Returns the server time in UTC."""
    return {
        "status": "ok",
        "service": "orbital-eye-backend",
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/orbit/ground-track")
def get_ground_track(
    altitude_km: float = Query(700.0, ge=200, le=2000),
    inclination_deg: float = Query(98.0, ge=0, le=180),
    step_s: float = Query(60.0, ge=1, le=600),
    orbits: float = Query(1.0, gt=0, le=3),
):
    """Simulated ground track for an idealized circular orbit."""
    period_s = orbital_period_s(altitude_km)
    points = ground_track(altitude_km, inclination_deg, period_s * orbits, step_s)
    return {
        "data_origin": "SIMULATED",
        "model": "idealized circular two-body orbit, spherical Earth, "
                 "Earth-fixed frame aligned with inertial at t=0",
        "period_s": period_s,
        "speed_km_s": circular_speed_km_s(altitude_km),
        "point_count": len(points),
        "points": points,
    }


@app.get("/api/orbit/tle-ground-track")
def get_tle_ground_track(
    step_s: float = Query(60.0, ge=1, le=600),
    duration_s: float = Query(5580.0, gt=0, le=20000),
):
    """SGP4 ground track from a built-in TEST-FIXTURE TLE (not live data)."""
    points = tle_ground_track(
        FIXTURE_LINE1, FIXTURE_LINE2, FIXTURE_START, duration_s, step_s
    )
    return {
        "data_origin": "SIMULATED",
        "orbit_source": "TEST_FIXTURE_TLE",
        "model": "SGP4 propagation; TEME rotated to ECEF with GMST (UT1=UTC); "
                 "spherical-Earth latitude",
        "warning": "TLE epoch is December 2019. This is not the satellite's "
                   "current position.",
        "tle_line1": FIXTURE_LINE1,
        "tle_line2": FIXTURE_LINE2,
        "point_count": len(points),
        "points": points,
    }
