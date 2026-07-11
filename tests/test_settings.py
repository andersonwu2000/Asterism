"""problem_settings chokepoint (frontmatter dissolve, 2026-07-07).

Load-bearing contracts:
  * dual-read: DB row wins; absent key falls back to the Manifest.
  * `effective_axioms` empty-never-weakens survives the DB path — an
    empty whitelist row still yields the framework defaults.
  * migration is idempotent and never clobbers a UI edit.
  * malformed DB rows are dropped (fallback), never honored.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db, manifest, settings


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.connect(tmp_path / "asterism.db")
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)", (db.now(),))
    c.commit()
    return c


def _mfst(**kw) -> manifest.Manifest:
    base = dict(problem="p", statement="True")
    base.update(kw)
    return manifest.Manifest(**base)


def test_keys_lockstep_with_ui_setting_keys() -> None:
    """Both stay literals (import would close a module cycle) — this
    pin is what keeps them from drifting apart."""
    assert settings.SETTING_KEYS == manifest.UI_SETTING_KEYS


def test_write_read_round_trip(conn) -> None:
    settings.write(conn, "p", "axioms_whitelist", ["propext", "Custom.ax"])
    settings.write(conn, "p", "library", True)
    got = settings.read(conn, "p")
    assert got["axioms_whitelist"] == ["propext", "Custom.ax"]
    assert got["library"] is True
    assert "forbidden_lemmas" not in got  # absent = fall back to file


def test_write_validates_key_and_type(conn) -> None:
    with pytest.raises(ValueError):
        settings.write(conn, "p", "no_such_key", [])
    with pytest.raises(ValueError):
        settings.write(conn, "p", "library", "yes")  # str is not bool
    with pytest.raises(ValueError):
        settings.write(conn, "p", "axioms_whitelist", "propext")  # not list


def test_read_missing_table_is_empty(tmp_path: Path) -> None:
    """A pre-settings DB opened read-only has no table — reads fall
    back to the file, never raise."""
    raw = sqlite3.connect(tmp_path / "bare.db")
    raw.row_factory = sqlite3.Row
    assert settings.read(raw, "p") == {}


def test_malformed_rows_are_dropped_not_honored(conn) -> None:
    """A corrupt row must fall back to the Manifest value — it can
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
    m = _mfst(axioms_whitelist=["file.ax"], library=False)
    settings.overlay(m, {"axioms_whitelist": ["db.ax"], "library": True})
    assert m.axioms_whitelist == ["db.ax"]
    assert m.library is True
    # untouched keys keep file values
    assert m.forbidden_lemmas == []


def test_empty_db_whitelist_never_weakens_the_gate(conn) -> None:
    """The soundness contract: an explicitly-empty DB whitelist still
    falls back to the framework defaults in effective_axioms — storing
    [] can never weaken a gate below the file semantics."""
    settings.write(conn, "p", "axioms_whitelist", [])
    m = _mfst(axioms_whitelist=["file.ax"])
    settings.overlay(m, settings.read(conn, "p"))
    assert m.axioms_whitelist == []
    manifest._default_axioms_warned.clear()
    wl = manifest.effective_axioms(m, problem="p")
    assert wl == list(manifest.FRAMEWORK_DEFAULT_AXIOMS)
    assert "sorryAx" not in wl


def test_migrate_is_idempotent_and_never_clobbers_db(conn) -> None:
    m = _mfst(axioms_whitelist=["file.ax"], forbidden_lemmas=["bad*"],
              library=True)
    assert settings.migrate_from_manifest(conn, "p", m) == 3
    # second run: nothing to do
    assert settings.migrate_from_manifest(conn, "p", m) == 0
    # a UI edit survives a re-migration against the stale file
    settings.write(conn, "p", "axioms_whitelist", ["ui.ax"])
    assert settings.migrate_from_manifest(conn, "p", m) == 0
    assert settings.read(conn, "p")["axioms_whitelist"] == ["ui.ax"]


def test_user_file_history_baseline_and_change(tmp_path: Path) -> None:
    """Self-audit 2026-07-12 §3-1b + §3-3: ManifestCache records a
    first-load baseline row per user-intent file (Manifest.md +
    Root.lean here) and one row per observed content change — via ANY
    write channel, no mtime signal on the Manifest needed; unchanged
    re-access records nothing."""
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    mpath = pdir / "Manifest.md"
    mpath.write_text("---\nproblem: p\n---\n\n# p\noriginal ask\n",
                     encoding="utf-8")
    (pdir / "Root.lean").write_text(
        "theorem main : True := by sorry\n", encoding="utf-8")
    conn = db.connect(tmp_path / "asterism.db")
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)", (db.now(),))
    conn.commit()

    cache = manifest.ManifestCache(tmp_path)
    assert cache.load("p", "Problems/p/Manifest.md") is not None
    rows = conn.execute(
        "SELECT file, sha, body FROM user_file_history WHERE problem='p'"
        " ORDER BY id").fetchall()
    assert {str(r["file"]) for r in rows} == {"Manifest.md", "Root.lean"}
    assert len(rows) == 2

    # Unchanged re-access: no new rows.
    _ = cache["p"]
    assert conn.execute("SELECT COUNT(*) AS n FROM user_file_history"
                        " WHERE problem='p'").fetchone()["n"] == 2

    # Root.lean tampered — Manifest mtime UNTOUCHED (the Bash-channel
    # shape): per-access sweep still records it.
    (pdir / "Root.lean").write_text(
        "theorem main : False := by sorry\n", encoding="utf-8")
    _ = cache["p"]
    root_rows = conn.execute(
        "SELECT sha FROM user_file_history WHERE problem='p'"
        " AND file='Root.lean' ORDER BY id").fetchall()
    assert len(root_rows) == 2
    assert root_rows[0]["sha"] != root_rows[1]["sha"]
    # Baseline helper: first row wins until an operator repin exists.
    assert manifest.user_file_baseline(conn, "p", "Root.lean") == str(
        root_rows[0]["sha"])
    conn.execute(
        "INSERT INTO user_file_history"
        " (problem, file, sha, body, seen_at, source)"
        " VALUES ('p', 'Root.lean', 'repinsha', 'x', ?, 'repin')",
        (db.now(),))
    conn.commit()
    assert manifest.user_file_baseline(conn, "p", "Root.lean") == "repinsha"
    conn.close()


def test_review_data_carries_manifest_section(tmp_path: Path) -> None:
    """The Ingest review snapshot covers the intent text: review_data
    returns the current Manifest body + the change-history metadata
    even for a problem with no deliverables."""
    from Tooling.quality import review
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n\n# p\nthe ask\n", encoding="utf-8")
    conn = db.connect(tmp_path / "asterism.db")
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)", (db.now(),))
    conn.commit()
    cache = manifest.ManifestCache(tmp_path)
    cache.load("p", "Problems/p/Manifest.md")   # baseline history row

    data = review.review_data(conn, tmp_path, problem="p")
    assert "the ask" in data["manifest"]["body"]
    assert len(data["manifest"]["history"]) == 1
    assert data["manifest"]["history"][0]["sha"]
    conn.close()


def test_manifest_cache_dual_read(tmp_path: Path) -> None:
    """The cache is THE overlay point: DB values win over the file,
    and a DB edit hot-reloads without any file-mtime signal."""
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\naxioms_whitelist:\n  - file.ax\n---\n\n# p\n",
        encoding="utf-8")
    conn = db.connect(tmp_path / "asterism.db")
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)", (db.now(),))
    conn.commit()

    cache = manifest.ManifestCache(tmp_path)
    m = cache.load("p", "Problems/p/Manifest.md")
    assert m is not None
    assert m.axioms_whitelist == ["file.ax"]  # no DB rows yet: file stands

    settings.write(conn, "p", "axioms_whitelist", ["db.ax"])
    # no file touch — the DB edit must still reach the next access
    assert cache["p"].axioms_whitelist == ["db.ax"]

    settings.write(conn, "p", "library", True)
    assert cache["p"].library is True
    conn.close()
