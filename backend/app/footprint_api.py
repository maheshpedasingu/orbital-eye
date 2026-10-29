from fastapi import APIRouter, Query

from app.orbit.footprint import footprint_radius_km

router = APIRouter()


@router.get("/api/orbit/footprint")
def get_footprint(
    altitude_km: float = Query(420.0, ge=200, le=2000),
    min_elevation_deg: float = Query(0.0, ge=0, le=89),
):
    """Horizon-limited visibility circle radius. Computed, not observed."""
    return {
        "data_origin": "SIMULATED",
        "model": "spherical Earth, horizon-limited visibility circle",
        "radius_km": footprint_radius_km(altitude_km, min_elevation_deg),
    }
