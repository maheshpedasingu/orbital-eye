from fastapi import APIRouter, Query

from app.orbit.pass_predictor import predict_all
from app.storage.db import connect

router = APIRouter()


@router.get("/api/passes/next")
def get_next_passes(hours: float = Query(72.0, gt=0, le=168),
                    limit: int = Query(5, ge=1, le=20)):
    """Upcoming observation opportunities over the AOI centre (PROPAGATED_FROM_REAL_TLE)."""
    conn = connect()
    try:
        return predict_all(conn, hours=hours, limit=limit)
    finally:
        conn.close()