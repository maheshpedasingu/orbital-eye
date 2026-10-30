from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from app.aoi import aoi_bbox, load_aoi
from app.geo_utils import haversine_km
from app.storage.db import connect

router = APIRouter()


def row_to_feature(row, centre_lat: float, centre_lon: float, box) -> dict:
    """One stored detection as a GeoJSON feature, labelled as unconfirmed."""
    west, south, east, north = box
    lat, lon = row["latitude_deg"], row["longitude_deg"]
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "data_origin": row["data_origin"],
            "status": "UNCONFIRMED_THERMAL_ANOMALY",
            "source": row["source"],
            "satellite": row["satellite"],
            "acquired_utc": row["acquired_utc"],
            "retrieved_utc": row["retrieved_utc"],
            "confidence_raw": row["confidence_raw"],
            "frp_mw": row["frp_mw"],
            "daynight": row["daynight"],
            "distance_to_aoi_centre_km": round(
                haversine_km(centre_lat, centre_lon, lat, lon), 1
            ),
            "inside_aoi_box": south <= lat <= north and west <= lon <= east,
        },
    }


@router.get("/api/fires")
def get_fires(days: float = Query(3.0, gt=0, le=30)):
    """Stored FIRMS thermal anomalies. Satellite-reported, NOT confirmed fires."""
    centre = load_aoi()["features"][0]["properties"]
    box = aoi_bbox(0.0)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM fire_detections WHERE acquired_utc >= ?"
            " ORDER BY acquired_utc DESC",
            (since,),
        ).fetchall()
        last_ok = conn.execute(
            "SELECT finished_utc FROM ingestion_runs WHERE status='ok'"
            " ORDER BY id DESC LIMIT 1"
        ).fetchone()
        last_run = conn.execute(
            "SELECT status, error FROM ingestion_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    return {
        "type": "FeatureCollection",
        "data_origin": "REAL_EXTERNAL",
        "note": "Satellite-reported thermal anomalies from NASA FIRMS. "
                "Not confirmed wildfires.",
        "count": len(rows),
        "last_successful_retrieval_utc": last_ok["finished_utc"] if last_ok else None,
        "last_run_status": last_run["status"] if last_run else None,
        "last_run_error": last_run["error"] if last_run else None,
        "features": [
            row_to_feature(
                r, centre["centre_lat_deg"], centre["centre_lon_deg"], box
            )
            for r in rows
        ],
    }
