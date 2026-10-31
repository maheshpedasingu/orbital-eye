import json
from datetime import datetime
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parents[3] / "config" / "alert_rules.json"
SEVERITY_RANK = {"INFO": 1, "WARNING": 2, "CRITICAL": 3}


def load_rules(path: Path = RULES_PATH) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def confidence_class(raw) -> str:
    """VIIRS confidence letter (l/n/h). Anything unrecognised counts as nominal."""
    c = (raw or "n").strip().lower()[:1]
    return c if c in ("l", "n", "h") else "n"


def zone_for(inside_box: bool, distance_km: float, rules: dict):
    if inside_box:
        return "inside"
    if distance_km <= rules["near_km"]:
        return "near"
    if distance_km <= rules["regional_km"]:
        return "regional"
    return None


def classify(acquired_utc, confidence_raw, distance_km, inside_box, rules, now) -> dict:
    """Decide what a detection means for alerting. Pure function, no I/O."""
    acquired = datetime.fromisoformat(acquired_utc)
    age_hours = (now - acquired).total_seconds() / 3600.0
    if age_hours > rules["max_age_hours"]:
        return {"outcome": "TOO_OLD", "severity": None, "zone": None}
    zone = zone_for(inside_box, distance_km, rules)
    if zone is None:
        return {"outcome": "OUT_OF_RANGE", "severity": None, "zone": None}
    severity = rules["severity_matrix"][zone].get(confidence_class(confidence_raw))
    if severity is None:
        return {"outcome": "BELOW_THRESHOLD", "severity": None, "zone": zone}
    return {"outcome": "OK", "severity": severity, "zone": zone}
