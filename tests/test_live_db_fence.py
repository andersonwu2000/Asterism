"""The live-data fence itself (task #180).

A fence nobody tests is a fence that quietly stops fencing — the
side-effect fence's own history says so (it was fixture DISCIPLINE for
months, and the day it silently lapsed cost a 20-minute green suite).
These tests pin both directions: the real files are unreachable, and the
legal test shapes stay reachable.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db

REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_DB = REPO_ROOT / "asterism.db"


def test_direct_connect_to_live_db_is_fenced():
    with pytest.raises(pytest.fail.Exception, match="live-data fence"):
        sqlite3.connect(str(LIVE_DB))


def test_readonly_uri_to_live_db_is_fenced():
    """`connect_readonly` builds a `file:...?mode=ro` URI. Reading live
    state cannot corrupt it, but it makes the test depend on whatever the
    daemon last wrote — an isolation defect the fence should still name."""
    with pytest.raises(pytest.fail.Exception, match="live-data fence"):
        db.connect_readonly(LIVE_DB)


def test_default_db_path_from_repo_root_is_fenced(monkeypatch):
    """The actual defect shape: a fixture forgets `monkeypatch.chdir`, so
    `db.DB_PATH` — a RELATIVE path — resolves against the repo root."""
    monkeypatch.chdir(REPO_ROOT)
    with pytest.raises(pytest.fail.Exception, match="live-data fence"):
        db.connect()


def test_backups_dir_is_fenced():
    """`.asterism/` holds the manual pre-migration snapshots. They are the
    recovery path, so they are protected on the same grounds as the DB."""
    with pytest.raises(pytest.fail.Exception, match="live-data fence"):
        sqlite3.connect(str(REPO_ROOT / ".asterism" / "backups" / "x.db"))


def test_in_memory_and_tmp_path_stay_open(tmp_path, monkeypatch):
    """The two legal shapes must be untouched — a fence that blocks the
    normal path just gets disabled."""
    sqlite3.connect(":memory:").close()

    monkeypatch.chdir(tmp_path)
    conn = db.connect()           # relative DB_PATH, now under tmp_path
    db.init_schema(conn)
    conn.close()
    assert (tmp_path / "asterism.db").exists()
    assert not LIVE_DB.samefile(tmp_path / "asterism.db")


def test_fence_matches_on_resolved_path(tmp_path, monkeypatch):
    """A copy of the live DB under tmp_path is legal: the fence compares
    resolved paths, not filenames."""
    (tmp_path / "asterism.db").write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    sqlite3.connect("asterism.db").close()
    with pytest.raises(pytest.fail.Exception, match="live-data fence"):
        sqlite3.connect(str(LIVE_DB))
