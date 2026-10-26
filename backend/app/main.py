from datetime import datetime, timezone

from fastapi import FastAPI, Query

from app.orbit.kepler import circular_speed_km_s, ground_track, orbital_period_s

app = FastAPI(title="ORBITAL-EYE API", version="0.1.0")


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
