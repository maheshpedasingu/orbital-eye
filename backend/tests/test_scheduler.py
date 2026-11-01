import os
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import system_api
from app.main import app
from app.scheduler import AlreadyRunning, acquire_lock, release_lock, run_once
from app.storage.db import connect
from app.task_log import ensure_task_table, is_due, last_attempt, last_success, record_task

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def ok_task(conn):
    return "ok", "fine"


def boom(conn):
    raise RuntimeError("kaboom")


def test_is_due_follows_the_interval(tmp_path):
    conn = connect(tmp_path / "t.db")
    ensure_task_table(conn)
    assert is_due(conn, "x", 60, NOW)
    record_task(conn, "x", NOW, NOW, "ok", "m")
    assert not is_due(conn, "x", 60, NOW + timedelta(minutes=30))
    assert is_due(conn, "x", 60, NOW + timedelta(minutes=61))
    assert is_due(conn, "x", 0, NOW)


def test_last_success_ignores_a_later_failure(tmp_path):
    conn = connect(tmp_path / "t.db")
    ensure_task_table(conn)
    record_task(conn, "x", NOW, NOW, "ok", "good")
    record_task(conn, "x", NOW + timedelta(hours=1), NOW, "failed", "bad")
    assert last_attempt(conn, "x")["status"] == "failed"
    assert last_success(conn, "x")["message"] == "good"


def test_second_instance_is_refused_until_the_lock_is_released(tmp_path):
    lock = tmp_path / "s.lock"
    acquire_lock(lock)
    with pytest.raises(AlreadyRunning):
        acquire_lock(lock)
    release_lock(lock)
    acquire_lock(lock)


def test_stale_lock_from_a_crash_is_replaced(tmp_path):
    lock = tmp_path / "s.lock"
    acquire_lock(lock)
    old = time.time() - 3600
    os.utime(lock, (old, old))
    acquire_lock(lock, stale_s=1800)


def test_one_crashing_task_does_not_stop_the_others(tmp_path):
    conn = connect(tmp_path / "t.db")
    res = run_once(conn, now=NOW, tasks=[("a", 0, boom), ("b", 0, ok_task)])
    assert [r["status"] for r in res] == ["failed", "ok"]
    assert "kaboom" in last_attempt(conn, "a")["message"]


def test_task_that_is_not_due_is_not_run(tmp_path):
    conn = connect(tmp_path / "t.db")
    calls = []

    def counting(c):
        calls.append(1)
        return "ok", "x"

    run_once(conn, now=NOW, tasks=[("a", 60, counting)])
    res = run_once(conn, now=NOW + timedelta(minutes=10), tasks=[("a", 60, counting)])
    assert res[0]["status"] == "not_due" and len(calls) == 1


def test_force_runs_a_task_that_is_not_due(tmp_path):
    conn = connect(tmp_path / "t.db")
    calls = []

    def counting(c):
        calls.append(1)
        return "ok", "x"

    run_once(conn, now=NOW, tasks=[("a", 60, counting)])
    run_once(conn, now=NOW + timedelta(minutes=10), tasks=[("a", 60, counting)], force=True)
    assert len(calls) == 2


def test_status_for_a_fresh_database(tmp_path, monkeypatch):
    monkeypatch.setattr(system_api, "connect", lambda: connect(tmp_path / "t.db"))
    data = TestClient(app).get("/api/system/status").json()
    assert [t["task"] for t in data["tasks"]] == ["firms", "alerts", "tle", "vegetation", "change"]
    assert all(t["never_run"] for t in data["tasks"])
    assert data["fire_detections"]["count"] == 0


def test_status_shows_the_last_success_and_the_later_failure(tmp_path, monkeypatch):
    dbfile = tmp_path / "t.db"
    conn = connect(dbfile)
    ensure_task_table(conn)
    record_task(conn, "firms", NOW, NOW, "ok", "good")
    record_task(conn, "firms", NOW + timedelta(hours=1), NOW, "failed", "bad")
    monkeypatch.setattr(system_api, "connect", lambda: connect(dbfile))
    data = TestClient(app).get("/api/system/status").json()
    firms = next(t for t in data["tasks"] if t["task"] == "firms")
    assert firms["status"] == "failed" and firms["message"] == "bad"
    assert firms["last_success_utc"] == NOW.isoformat()