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

