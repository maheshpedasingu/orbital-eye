import csv
import io
import math
from datetime import datetime, timezone

import httpx

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api"
REQUIRED_COLUMNS = ("latitude", "longitude", "acq_date", "acq_time")


def redact(text: str, key: str) -> str:
    """Remove the secret key from any text before it is shown or logged."""
    return text.replace(key, "***")


def check_data_availability(key: str, sensor: str = "VIIRS_SNPP_NRT") -> str:
    """Ask FIRMS which dates are available for a sensor. Returns CSV text."""
    url = f"{BASE_URL}/data_availability/csv/{key}/{sensor}"
    try:
        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()
        return response.text
    except Exception as exc:
        raise RuntimeError(redact(f"FIRMS request failed: {exc}", key)) from None


def build_area_url(key, source, bbox, day_range) -> str:
    west, south, east, north = bbox
    return f"{BASE_URL}/area/csv/{key}/{source}/{west},{south},{east},{north}/{day_range}"


def fetch_area_csv(key: str, source: str, bbox, day_range: int = 2) -> str:
    """Download detections (CSV text) for a box. Day range is 1 to 10."""
    if not 1 <= day_range <= 10:
        raise ValueError("day_range must be between 1 and 10")
    url = build_area_url(key, source, bbox, day_range)
    try:
        response = httpx.get(url, timeout=60.0)
        response.raise_for_status()
        return response.text
    except Exception as exc:
        raise RuntimeError(redact(f"FIRMS request failed: {exc}", key)) from None


def _number(rec: dict, name: str, required: bool = False):
    raw = rec.get(name, "")
    if raw == "":
        if required:
            raise ValueError(f"missing {name}")
        return None
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{name} is not a number: {raw!r}") from None
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"{name} is not finite")
    return value


def _validate_row(rec: dict, bbox) -> dict:
    west, south, east, north = bbox
    lat = _number(rec, "latitude", required=True)
    lon = _number(rec, "longitude", required=True)
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError("coordinates out of range")
    if not (south <= lat <= north and west <= lon <= east):
        raise ValueError("outside the requested box")

    date = rec.get("acq_date", "")
    hhmm = rec.get("acq_time", "").zfill(4)
    try:
        acquired = datetime.strptime(f"{date} {hhmm}", "%Y-%m-%d %H%M")
    except ValueError:
        raise ValueError(f"bad acquisition time {date!r} {hhmm!r}") from None
    acquired = acquired.replace(tzinfo=timezone.utc)

    frp = _number(rec, "frp")
    if frp is not None and frp < 0:
        raise ValueError("negative frp")
    brightness = _number(rec, "bright_ti4")
    if brightness is None:
        brightness = _number(rec, "brightness")

    return {
        "latitude_deg": lat,
        "longitude_deg": lon,
        "acquired_utc": acquired.isoformat(),
        "satellite": rec.get("satellite") or None,
        "instrument": rec.get("instrument") or None,
        "confidence_raw": rec.get("confidence") or None,
        "frp_mw": frp,
        "brightness_k": brightness,
        "daynight": rec.get("daynight") or None,
    }


def parse_detections(csv_text: str, bbox) -> tuple[list[dict], list[dict]]:
    """Validate FIRMS CSV text. Returns (valid_rows, rejected_rows).

    Raises ValueError if the response is not a FIRMS detection CSV. A header
    with no rows is valid and means "no detections".
    """
    rows = list(csv.reader(io.StringIO(csv_text.strip())))
    if not rows or rows == [[]]:
        raise ValueError("Empty response from FIRMS")
    header = [h.strip().lower() for h in rows[0]]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ValueError(
            f"Unexpected FIRMS response: missing columns {missing}; "
            f"starts with {csv_text[:80]!r}"
        )
    valid, rejected = [], []
    for line_no, values in enumerate(rows[1:], start=2):
        rec = dict(zip(header, (v.strip() for v in values)))
        try:
            valid.append(_validate_row(rec, bbox))
        except ValueError as exc:
            rejected.append({"line": line_no, "reason": str(exc)})
    return valid, rejected
