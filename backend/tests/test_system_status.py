import os
import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import system_api
from app.main import app
from app.storage.db import connect
from app.task_log import ensure_task_table, record_task

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def test_never_succeeded_is_overdue():
    assert system_api.is_overdue(None, 60, NOW)


def test_overdue_threshold_is_three_intervals():
    assert not system_api.is_overdue((NOW - timedelta(minutes=179)).isoformat(), 60, NOW)
    assert system_api.is_overdue((NOW - timedelta(minutes=181)).isoformat(), 60, NOW)


def test_scheduler_running_follows_the_lock_file_age(tmp_path, monkeypatch):
    lock = tmp_path / "s.lock"
    monkeypatch.setattr(system_api, "LOCK_PATH", lock)
    assert not system_api.scheduler_running()          # no lock file
    lock.write_text("1")
    assert system_api.scheduler_running()              # just written
    old = time.time() - 3600
    os.utime(lock, (old, old))
    assert not system_api.scheduler_running()          # left over from a crash


def test_fresh_database_reports_everything_overdue(tmp_path, monkeypatch):
    monkeypatch.setattr(system_api, "connect", lambda: connect(tmp_path / "t.db"))
    monkeypatch.setattr(system_api, "LOCK_PATH", tmp_path / "none.lock")
    data = TestClient(app).get("/api/system/status").json()
    assert data["scheduler_running"] is False
    assert all(t["never_run"] and t["overdue"] for t in data["tasks"])
    assert data["fire_detections"]["count"] == 0


def test_recent_success_is_not_overdue_and_a_failure_does_not_hide_it(tmp_path, monkeypatch):
    dbfile = tmp_path / "t.db"
    conn = connect(dbfile)
    ensure_task_table(conn)
    recent = datetime.now(timezone.utc) - timedelta(minutes=10)
    record_task(conn, "firms", recent, recent, "ok", "good")
    record_task(conn, "firms", recent + timedelta(minutes=5), recent, "failed", "bad")
    monkeypatch.setattr(system_api, "connect", lambda: connect(dbfile))
    firms = next(t for t in TestClient(app).get("/api/system/status").json()["tasks"]
                 if t["task"] == "firms")
    assert firms["status"] == "failed" and firms["message"] == "bad"
    assert firms["last_success_utc"] == recent.isoformat()
    assert firms["overdue"] is False