from fastapi.testclient import TestClient

from app import alerts_api
from app.main import app


def test_simulated_origin_is_empty_when_no_simulation_file(tmp_path, monkeypatch):
    monkeypatch.setattr(alerts_api, "SIM_DB_PATH", tmp_path / "missing.db")
    r = TestClient(app).get("/api/alerts?origin=simulated")
    assert r.status_code == 200
    assert r.json()["count"] == 0
    assert r.json()["origin"] == "simulated"


def test_unknown_origin_is_rejected():
    assert TestClient(app).get("/api/alerts?origin=banana").status_code == 422
