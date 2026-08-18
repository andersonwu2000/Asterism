"""problem_settings chokepoint (frontmatter dissolve, 2026-07-07;
sole source since the v40 Manifest retirement).

Load-bearing contracts:
  * a key PRESENT in the DB is the value; an ABSENT key means the
    framework default (no file fallback exists anymore).
  * `effective_axioms` empty-never-weakens survives the DB path — an
    empty whitelist row still yields the framework defaults.
  * malformed DB rows are dropped (default), never honored.
  * IntentCache re-reads the DB per access — a DB edit is live on the
    next access with no file-mtime signal.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db, intent, settings


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.connect(tmp_path / "asterism.db")
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES ('p', ?)", (db.now(),))
    c.commit()
    return c


def _intent(**kw) -> intent.ProblemIntent:
    base = dict(problem="p", charter="True")
    base.update(kw)
    return intent.ProblemIntent(**base)


def test_write_read_round_trip(conn) -> None:
    settings.write(conn, "p", "axioms_whitelist", ["propext", "Custom.ax"])
    settings.write(conn, "p", "library", True)
    settings.write(conn, "p", "signoff", False)
    got = settings.read(conn, "p")
    assert got["axioms_whitelist"] == ["propext", "Custom.ax"]
    assert got["library"] is True
    assert got["signoff"] is False
    assert "forbidden_lemmas" not in got  # absent = framework default


def test_write_validates_key_and_type(conn) -> None:
    with pytest.raises(ValueError):
        settings.write(conn, "p", "no_such_key", [])
    with pytest.raises(ValueError):
        settings.write(conn, "p", "library", "yes")  # str is not bool
    with pytest.raises(ValueError):
        settings.write(conn, "p", "axioms_whitelist", "propext")  # not list


def test_read_missing_table_is_empty(tmp_path: Path) -> None:
    """A pre-settings DB opened read-only has no table — reads fall
    back to the framework defaults, never raise."""
    raw = sqlite3.connect(tmp_path / "bare.db")
    raw.row_factory = sqlite3.Row
    assert settings.read(raw, "p") == {}


def test_malformed_rows_are_dropped_not_honored(conn) -> None:
    """A corrupt row must fall back to the framework default — it can
    never hand a gate different settings than validation would allow."""
    conn.execute(
        "INSERT INTO problem_settings (problem, key, value, updated_at)"
        " VALUES ('p', 'axioms_whitelist', 'not json{', ?)", (db.now(),))
    conn.execute(
        "INSERT INTO problem_settings (problem, key, value, updated_at)"
        " VALUES ('p', 'library', '\"yes\"', ?)", (db.now(),))  # wrong type
    conn.commit()
    assert settings.read(conn, "p") == {}


def test_overlay_stamps_dataclass_fields(conn) -> None:
    pi = _intent(axioms_whitelist=["seed.ax"], library=False)
    settings.overlay(pi, {"axioms_whitelist": ["db.ax"], "library": True})
    assert pi.axioms_whitelist == ["db.ax"]
    assert pi.library is True
    # untouched keys keep their prior values
    assert pi.forbidden_lemmas == []


def test_empty_db_whitelist_never_weakens_the_gate(conn) -> None:
    """The soundness contract: an explicitly-empty DB whitelist still
    falls back to the framework defaults in effective_axioms — storing
    [] can never weaken a gate below the default semantics."""
    settings.write(conn, "p", "axioms_whitelist", [])
    pi = _intent(axioms_whitelist=["seed.ax"])
    settings.overlay(pi, settings.read(conn, "p"))
    assert pi.axioms_whitelist == []
    intent._default_axioms_warned.clear()
    wl = intent.effective_axioms(pi, problem="p")
    assert wl == list(intent.FRAMEWORK_DEFAULT_AXIOMS)
    assert "sorryAx" not in wl


def test_user_file_history_baseline_and_change(tmp_path: Path) -> None:
    """Self-audit 2026-07-12 §3-1b + §3-3, v40 edition: IntentCache
    records a first-load baseline row per user-intent FILE (Root.lean +
    Defs.lean) and one row per observed content change — via ANY write
    channel, no mtime signal needed; unchanged re-access records
    nothing."""
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "Defs.lean").write_text(
        "def answer : Nat := 42\n", encoding="utf-8")
    (pdir / "Root.lean").write_text(
        "theorem main : True := by sorry\n", encoding="utf-8")
    conn = db.connect(tmp_path / "asterism.db")
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES ('p', ?)", (db.now(),))
    conn.commit()

    cache = intent.IntentCache(tmp_path)
    assert cache.load("p") is not None
    rows = conn.execute(
        "SELECT file, sha, body FROM user_file_history WHERE problem='p'"
        " ORDER BY id").fetchall()
    assert {str(r["file"]) for r in rows} == {"Defs.lean", "Root.lean"}
    assert len(rows) == 2

    # Unchanged re-access: no new rows.
    _ = cache["p"]
    assert conn.execute("SELECT COUNT(*) AS n FROM user_file_history"
                        " WHERE problem='p'").fetchone()["n"] == 2

    # Root.lean tampered — no other signal (the Bash-channel shape):
    # per-access sweep still records it.
    (pdir / "Root.lean").write_text(
        "theorem main : False := by sorry\n", encoding="utf-8")
    _ = cache["p"]
    root_rows = conn.execute(
        "SELECT sha FROM user_file_history WHERE problem='p'"
        " AND file='Root.lean' ORDER BY id").fetchall()
    assert len(root_rows) == 2
    assert root_rows[0]["sha"] != root_rows[1]["sha"]
    # Baseline helper: first row wins until an operator repin exists.
    assert intent.user_file_baseline(conn, "p", "Root.lean") == str(
        root_rows[0]["sha"])
    conn.execute(
        "INSERT INTO user_file_history"
        " (problem, file, sha, body, seen_at, source)"
        " VALUES ('p', 'Root.lean', 'repinsha', 'x', ?, 'repin')",
        (db.now(),))
    conn.commit()
    assert intent.user_file_baseline(conn, "p", "Root.lean") == "repinsha"
    conn.close()


def test_review_data_carries_intent_section(tmp_path: Path) -> None:
    """The Ingest review snapshot covers the intent text: review_data
    returns the current charter body + the change-history metadata even
    for a problem with no deliverables."""
    from Tooling.quality import review
    from Tooling.state import groups
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    conn = db.connect(tmp_path / "asterism.db")
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES ('p', ?)", (db.now(),))
    conn.commit()
    groups.ensure_top_group(conn, "p")
    intent.set_charter(conn, "p", "the ask", source="observed")  # baseline

    data = review.review_data(conn, tmp_path, problem="p")
    assert "the ask" in data["manifest"]["body"]
    assert len(data["manifest"]["history"]) == 1
    assert data["manifest"]["history"][0]["sha"]
    conn.close()


def test_intent_cache_db_edit_hot_reloads(tmp_path: Path) -> None:
    """The cache re-reads the DB per access: a settings edit reaches
    the next access with no file-mtime signal involved."""
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    conn = db.connect(tmp_path / "asterism.db")
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES ('p', ?)", (db.now(),))
    conn.commit()

    cache = intent.IntentCache(tmp_path)
    pi = cache.load("p")
    assert pi is not None
    assert pi.axioms_whitelist == []  # no DB rows yet: framework default

    settings.write(conn, "p", "axioms_whitelist", ["db.ax"])
    # no file touch — the DB edit must still reach the next access
    assert cache["p"].axioms_whitelist == ["db.ax"]

    settings.write(conn, "p", "library", True)
    assert cache["p"].library is True
    conn.close()
