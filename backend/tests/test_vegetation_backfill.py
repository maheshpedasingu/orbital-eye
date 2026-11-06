from app.analysis.vegetation_backfill import run_backfill, select_scenes


def _s(sid, dt, cloud, bands=("red", "nir", "scl")):
    return {"id": sid, "datetime": dt, "cloud_cover": cloud,
            "bands": {b: {} for b in bands}}


def test_select_filters_and_orders_newest_first():
    sums = [
        _s("old", "2026-09-01T00:00:00Z", 10),
        _s("cloudy", "2026-10-10T00:00:00Z", 80),
        _s("nobands", "2026-10-11T00:00:00Z", 5, bands=("red",)),
        _s("nocloud", "2026-10-12T00:00:00Z", None),
        _s("new", "2026-10-20T00:00:00Z", 20),
    ]
    got = select_scenes(sums, 40.0, 10)
    assert [s["id"] for s in got] == ["new", "old"]


def test_select_respects_limit():
    sums = [_s(str(i), f"2026-10-{i + 1:02d}T00:00:00Z", 5) for i in range(5)]
    assert len(select_scenes(sums, 40.0, 2)) == 2


def test_run_backfill_runs_job_once_per_scene(monkeypatch):
    sums = [_s("a", "2026-10-01T00:00:00Z", 5), _s("b", "2026-10-02T00:00:00Z", 5)]
    seen = []

    def fake_job(conn, finder=None, **kw):
        scene = finder("c", None, 1, 1)
        seen.append(scene["id"])
        return {"status": "ok", "scene_id": scene["id"]}

    import app.analysis.vegetation_backfill as vb
    monkeypatch.setattr(vb, "summarize_item", lambda x: x)
    res = run_backfill(None, searcher=lambda c, b, days: sums, job=fake_job)
    assert seen == ["b", "a"] and len(res) == 2
