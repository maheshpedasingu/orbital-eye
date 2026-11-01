from datetime import datetime, timedelta, timezone

import httpx

GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
HEADERS = {"User-Agent": "ORBITAL-EYE/0.1 (learning project)"}
MIN_FETCH_INTERVAL_HOURS = 12


def tle_checksum_ok(line: str) -> bool:
    """TLE checksum: sum of digits (each '-' counts 1) modulo 10 equals the last digit."""
    if len(line) != 69 or not line[68].isdigit():
        return False
    total = 0
    for ch in line[:68]:
        if ch.isdigit():
            total += int(ch)
        elif ch == "-":
            total += 1
    return total % 10 == int(line[68])


def parse_epoch(line1: str) -> datetime:
    """Epoch (UTC) from TLE line 1: columns 19-20 year, 21-32 day of year."""
    yy = int(line1[18:20])
    day = float(line1[20:32])
    year = 2000 + yy if yy < 57 else 1900 + yy
    return datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1.0)


def parse_3le(text: str, expected_catnr: int) -> dict:
    """Validate a 3-line response (name + two TLE lines). Raises ValueError."""
    lines = [ln.rstrip() for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) != 3:
        raise ValueError(
            f"expected 3 lines (name and two TLE lines), got {len(lines)}; "
            f"response starts with {text[:80]!r}"
        )
    name, line1, line2 = lines
    if len(line1) != 69 or len(line2) != 69 \
            or not line1.startswith("1 ") or not line2.startswith("2 "):
        raise ValueError("response is not a valid two-line element set")
    if not (tle_checksum_ok(line1) and tle_checksum_ok(line2)):
        raise ValueError("TLE checksum failed")
    cat1, cat2 = int(line1[2:7]), int(line2[2:7])
    if cat1 != cat2:
        raise ValueError("the two TLE lines have different catalogue numbers")
    if cat1 != expected_catnr:
        raise ValueError(f"asked for {expected_catnr} but received {cat1}")
    return {
        "name": name.strip(),
        "catnr": cat1,
        "line1": line1,
        "line2": line2,
        "epoch_utc": parse_epoch(line1).isoformat(),
    }


def fetch_3le(catnr: int) -> str:
    """Download the current element set (FORMAT is always explicit)."""
    try:
        r = httpx.get(GP_URL, params={"CATNR": catnr, "FORMAT": "3LE"},
                      headers=HEADERS, timeout=30.0)
        r.raise_for_status()
        return r.text
    except Exception as exc:
        raise RuntimeError(f"CelesTrak request failed: {exc}") from None