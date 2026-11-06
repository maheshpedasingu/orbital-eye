from datetime import datetime

from app.geo_utils import haversine_km


def corroborate(detections, radius_km=1.5, window_minutes=180, key="satellite") -> list[dict]:
    """Group detections that different satellites report at nearly the same place and time.

    Pure function. Returns clusters seen by at least two distinct satellites.
    Corroboration is stronger evidence than a single detection, but it is
    still NOT a confirmed wildfire.
    """
    dets = [dict(d) for d in detections]
    n = len(dets)
    times = [datetime.fromisoformat(d["acquired_utc"]) for d in dets]
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            a, b = dets[i], dets[j]
            if a["data_origin"] != b["data_origin"]:
                continue
            if a.get(key) is None or b.get(key) is None or a[key] == b[key]:
                continue
            if abs((times[i] - times[j]).total_seconds()) / 60.0 > window_minutes:
                continue
            if haversine_km(a["latitude_deg"], a["longitude_deg"],
                            b["latitude_deg"], b["longitude_deg"]) <= radius_km:
                parent[find(i)] = find(j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    clusters = []
    for members in groups.values():
        sats = sorted({dets[i][key] for i in members if dets[i].get(key) is not None})
        if len(sats) < 2:
            continue
        ts = sorted(times[i] for i in members)
        clusters.append({
            "data_origin": dets[members[0]]["data_origin"],
            "satellites": sats,
            "detection_ids": sorted(dets[i]["id"] for i in members),
            "n_detections": len(members),
            "latitude_deg": sum(dets[i]["latitude_deg"] for i in members) / len(members),
            "longitude_deg": sum(dets[i]["longitude_deg"] for i in members) / len(members),
            "first_acquired_utc": ts[0].isoformat(),
            "last_acquired_utc": ts[-1].isoformat(),
            "span_minutes": round((ts[-1] - ts[0]).total_seconds() / 60.0, 1),
        })
    clusters.sort(key=lambda c: c["last_acquired_utc"], reverse=True)
    return clusters
