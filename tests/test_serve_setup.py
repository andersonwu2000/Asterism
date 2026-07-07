"""Setup-wizard API contract (/api/setup/*): cheap side-effect-free
status, validated lake-path adoption, named async jobs. No network,
no real installs — workers are monkeypatched.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Tooling.serve.app import create_app
from Tooling.state import db


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "Problems").mkdir()
    return tmp_path


def _client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


def test_setup_status_shape(workspace: Path, monkeypatch) -> None:
    # the fence rightly blocks a real `lake --version` spawn — the
    # status shape is the thing under test
    from Tooling.serve import setup as _setup
    monkeypatch.setattr(_setup, "lake_status",
                        lambda: {"found": True, "path": "X:/lake",
                                 "version": "Lake 5.0"})
    st = _client(workspace).get("/api/setup/status").json()
    assert set(st) >= {"repo", "lake", "mathlib", "claude", "elan_home",
                       "disks", "update"}
    assert set(st["lake"]) == {"found", "path", "version"}
    assert st["mathlib"] == {"present": False}  # tmp workspace: no cache
    assert isinstance(st["disks"], list)
    assert st["update"] is None  # release-download hook, not wired yet


def test_setup_lake_path_validates_by_running(workspace: Path) -> None:
    c = _client(workspace)
    r = c.post("/api/setup/lake-path", json={"path": "C:/no/such/lake"})
    assert r.status_code == 422
    assert "no lake" in r.json()["detail"]


def test_setup_jobs_idle_then_stubbed_run(workspace: Path,
                                          monkeypatch) -> None:
    from Tooling.serve import setup as _setup
    c = _client(workspace)
    assert c.get("/api/setup/job/lean").json()["state"] == "idle"

    # stub the worker: the job machinery (state + log tail) is the
    # thing under test, not elan
    def fake_worker(_home: str):
        def worker(log):  # noqa: ANN001
            log("hello from the stub")
            return 0
        return worker
    monkeypatch.setattr(_setup, "_install_lean_worker", fake_worker)
    monkeypatch.setattr(_setup.sys, "platform", "win32")
    r = c.post("/api/setup/install-lean", json={"elan_home": "X:/elan"})
    assert r.json()["state"] == "running"
    # the stub finishes almost instantly
    import time
    for _ in range(50):
        j = c.get("/api/setup/job/lean").json()
        if j["state"] != "running":
            break
        time.sleep(0.05)
    assert j["state"] == "done"
    assert "hello from the stub" in j["log"]


def test_setup_mathlib_requires_lake(workspace: Path,
                                     monkeypatch) -> None:
    from Tooling.serve import setup as _setup
    monkeypatch.setattr(_setup, "lake_status",
                        lambda: {"found": False, "path": None,
                                 "version": None})
    r = _client(workspace).post("/api/setup/fetch-mathlib")
    assert r.status_code == 409
    assert "Lean first" in r.json()["detail"]
