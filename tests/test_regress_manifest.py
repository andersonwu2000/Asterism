"""Regression manifest (state/regress.py + `asterism regress`, task #8).

Schema guard over the TRACKED Benchmarks/proved_manifest.jsonl (hand-edit
protection), plus behavior tests of the recorder (best-effort contract)
and the report's status semantics (RESET = candidate, not error).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from Tooling.state import db, regress

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------
# Tracked-file schema guard
# ---------------------------------------------------------------------

def test_tracked_manifest_schema():
    path = ROOT / regress.MANIFEST_REL
    assert path.is_file(), "Benchmarks/proved_manifest.jsonl missing"
    for i, ln in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1):
        if not ln.strip():
            continue
        e = json.loads(ln)          # every line parses
        assert e.get("problem"), f"line {i}: empty problem"
        assert e.get("terminal") in regress.TERMINALS, f"line {i}"
        # commit: short hex, or the sanctioned sentinels
        c = str(e.get("commit", ""))
        assert c in ("backfill", "unknown") or (
            6 <= len(c) <= 40 and all(ch in "0123456789abcdef" for ch in c)
        ), f"line {i}: bad commit {c!r}"
        assert e.get("at"), f"line {i}: missing timestamp"


# ---------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------

def _git_init(ws: Path) -> None:
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=str(ws), check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "x"],
                   cwd=str(ws), check=True)


def test_record_terminal_appends_and_never_raises(tmp_path):
    _git_init(tmp_path)
    (tmp_path / "lean-toolchain").write_text("x", encoding="utf-8")
    regress.record_terminal(tmp_path, problem="p", terminal="ingested",
                            deliverables=3)
    regress.record_terminal(tmp_path, problem="p", terminal="bridged",
                            harvest_files=6)
    entries = regress.load(tmp_path)
    assert [e["terminal"] for e in entries] == ["ingested", "bridged"]
    assert entries[0]["deliverables"] == 3
    assert entries[1]["harvest_files"] == 6
    assert all(len(e["commit"]) == 12 for e in entries)   # real git head

    # best-effort: an unwritable manifest must not raise
    import Tooling.state.regress as r
    bad = tmp_path / "Benchmarks" / "proved_manifest.jsonl"
    bad.unlink()
    bad.mkdir()                     # a DIRECTORY at the file path
    regress.record_terminal(tmp_path, problem="p", terminal="ingested")


# ---------------------------------------------------------------------
# Report semantics
# ---------------------------------------------------------------------

def _mem() -> sqlite3.Connection:
    conn = db.connect(":memory:")
    db.init_schema(conn)
    return conn


def _seed(conn, name, *, ingested=False, bridged=False):
    conn.execute(
        "INSERT INTO problems (name, created_at,"
        " bootstrap_done) VALUES (?, ?, 1)", (name, db.now()))
    if ingested:
        db.set_problem_ingested(conn, name)
    if bridged:
        db.mark_library_bridged(conn, name)
    conn.commit()


def test_report_statuses(tmp_path, monkeypatch):
    from Tooling.quality import lean_contracts
    monkeypatch.setattr(lean_contracts, "toolchain_fingerprint",
                        lambda ws: "f" * 40)
    cur_fp = ("f" * 40)[:16]
    entries = [
        {"problem": "ok_p", "terminal": "ingested", "commit": "abc123abc123",
         "toolchain": cur_fp, "at": "t"},
        {"problem": "reset_p", "terminal": "bridged",
         "commit": "abc123abc123", "toolchain": cur_fp, "at": "t"},
        {"problem": "partial_p", "terminal": "bridged",
         "commit": "abc123abc123", "toolchain": cur_fp, "at": "t"},
        {"problem": "drift_p", "terminal": "ingested",
         "commit": "abc123abc123", "toolchain": "0" * 16, "at": "t"},
    ]
    mpath = tmp_path / regress.MANIFEST_REL
    mpath.parent.mkdir(parents=True)
    mpath.write_text("\n".join(json.dumps(e) for e in entries) + "\n",
                     encoding="utf-8")
    conn = _mem()
    _seed(conn, "ok_p", ingested=True)
    # reset_p: not in DB at all
    _seed(conn, "partial_p", ingested=True)          # bridged undone
    _seed(conn, "drift_p", ingested=True)
    by_status = {s: m for s, m in regress.report(conn, tmp_path)}
    assert "ok_p: ingested (still holds)" in by_status["OK"]
    assert "reset_p" in by_status["RESET"]
    assert "partial_p" in by_status["PARTIAL"]
    assert "drift_p" in by_status["DRIFT"]


def test_report_latest_line_wins(tmp_path, monkeypatch):
    """Append-only history: a re-proved problem's LATEST line is the
    expectation (older lines are records, not requirements)."""
    from Tooling.quality import lean_contracts
    monkeypatch.setattr(lean_contracts, "toolchain_fingerprint",
                        lambda ws: "f" * 40)
    cur_fp = ("f" * 40)[:16]
    entries = [
        {"problem": "p", "terminal": "bridged", "commit": "aaaaaaaaaaaa",
         "toolchain": "0" * 16, "at": "t1"},
        {"problem": "p", "terminal": "ingested", "commit": "bbbbbbbbbbbb",
         "toolchain": cur_fp, "at": "t2"},
    ]
    mpath = tmp_path / regress.MANIFEST_REL
    mpath.parent.mkdir(parents=True)
    mpath.write_text("\n".join(json.dumps(e) for e in entries) + "\n",
                     encoding="utf-8")
    conn = _mem()
    _seed(conn, "p", ingested=True)
    findings = regress.report(conn, tmp_path)
    assert findings == [("OK", "p: ingested (still holds)")]
