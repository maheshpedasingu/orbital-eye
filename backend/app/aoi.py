import json
from pathlib import Path

from fastapi import APIRouter

AOI_PATH = Path(__file__).resolve().parents[2] / "config" / "aoi_vijayawada.geojson"

router = APIRouter()


def load_aoi() -> dict:
    """Load the configured area of interest (GeoJSON, [lon, lat] order)."""
    with open(AOI_PATH, encoding="utf-8-sig") as f:
        return json.load(f)


@router.get("/api/aoi")
def get_aoi():
    """The configured area of interest. This is configuration, not observation data."""
    return {"data_origin": "CONFIG", "aoi": load_aoi()}



def aoi_bbox(pad_deg: float = 0.0) -> tuple[float, float, float, float]:
    """(west, south, east, north) in degrees around the AOI, plus a margin."""
    ring = load_aoi()["features"][0]["geometry"]["coordinates"][0]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (
        round(min(lons) - pad_deg, 3),
        round(min(lats) - pad_deg, 3),
        round(max(lons) + pad_deg, 3),
        round(max(lats) + pad_deg, 3),
    )
