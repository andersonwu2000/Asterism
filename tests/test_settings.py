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
