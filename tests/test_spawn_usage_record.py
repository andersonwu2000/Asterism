"""spawn_usage recorder — exact-snapshot dedup (#126).

The usage block in `_parser_state.json` is the SESSION-CUMULATIVE
snapshot; tail hooks (feedback / reflection resumes) re-enter the
recorder with the same numbers under their own kind label. Before the
dedup, 51% of historical rows were byte-identical five-tuples and every
SUM-based cost report double-counted.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from Tooling.agent.runtime import _record_spawn_usage
from Tooling.state import db


def _setup(tmp_path: Path):
    c = db.connect(tmp_path / "asterism.db")
    db.init_schema(c)
    c.close()
    attempts = tmp_path / ".attempts" / "pid-1"
    attempts.mkdir(parents=True)
    return attempts


def _write_state(attempts: Path, *, out: int, turns: int) -> None:
    (attempts / "_parser_state.json").write_text(json.dumps({
        "usage": {"input_tokens": 5, "output_tokens": out,
                  "cache_read_input_tokens": 50,
                  "cache_creation_input_tokens": 20,
                  "turns": turns}}), encoding="utf-8")


def _record(tmp_path: Path, attempts: Path, kind: str,
            wall: float = 1.0) -> None:
    _record_spawn_usage(kind=kind, attempts_dir=attempts,
                        problem_dir=tmp_path / "Problems" / "p",
                        wall_sec=wall, workspace=tmp_path, problem="p",
                        pipeline_id="pid-1")


def test_same_snapshot_recorded_once(tmp_path: Path) -> None:
    """Work turn records; the tail hook re-reads the identical snapshot
    (different kind label) and must NOT add a second row — the first
    record (true kind, true wall time) wins."""
    attempts = _setup(tmp_path)
    _write_state(attempts, out=100, turns=3)
    _record(tmp_path, attempts, "formalizer")
    _record(tmp_path, attempts, "forward")  # tail hook, same snapshot
    c = sqlite3.connect(tmp_path / "asterism.db")
    c.row_factory = sqlite3.Row
    rows = list(c.execute("SELECT kind FROM spawn_usage"))
    assert len(rows) == 1
    assert rows[0]["kind"] == "formalizer"


def test_progressed_snapshot_records_second_row(tmp_path: Path) -> None:
    """Legitimate multi-stage accounting stays: intake turn then work
    turn write DIFFERENT cumulative snapshots — both rows kept."""
    attempts = _setup(tmp_path)
    _write_state(attempts, out=100, turns=3)
    _record(tmp_path, attempts, "formalizer")
    _write_state(attempts, out=180, turns=5)
    _record(tmp_path, attempts, "formalizer", wall=2.0)
    c = sqlite3.connect(tmp_path / "asterism.db")
    n = c.execute("SELECT COUNT(*) FROM spawn_usage").fetchone()[0]
    assert n == 2
