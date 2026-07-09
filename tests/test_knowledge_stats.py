"""knowledge_stats — offline knowledge-layer ROI telemetry (read-only)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from Tooling.quality import knowledge_stats as ks
from Tooling.state import db as _db

P = "Test.kstats"


def _setup(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "asterism.db"))
    conn.row_factory = sqlite3.Row
    _db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, manifest_path, created_at)"
                 " VALUES (?, 'Problems/Test/kstats/Manifest.md', ?)",
                 (P, _db.now()))
    conn.commit()
    return conn


def test_presearch_hit_rate(tmp_path: Path) -> None:
    conn = _setup(tmp_path)
    pdir = tmp_path / "Problems" / "Test" / "kstats"
    (pdir / ".presearch").mkdir(parents=True)
    (pdir / "proofs").mkdir()
    gid = _db.insert_goal(
        conn, problem=P, slug="uses_one",
        lean_path="Problems/Test/kstats/proofs/L_uses_one.lean",
        statement="T", origin="backward", status="proved")
    (pdir / ".presearch" / f"g{gid}.md").write_text(
        "## Candidate lemmas (pre-search)\n\n"
        "- `Nat.add_comm`  [mathlib] — commutativity\n"
        "- `Finset.sum_le_sum`  [mathlib]\n", encoding="utf-8")
    (pdir / "proofs" / "L_uses_one.lean").write_text(
        "theorem uses_one : True := by\n"
        "  -- Finset.sum_le_sum only in a comment: must not count\n"
        "  exact (Nat.add_comm 1 2) ▸ trivial\n", encoding="utf-8")
    conn.commit()

    st = ks.presearch_stats(conn, tmp_path, problem_like=P)
    assert st["proved_with_candidates"] == 1
    assert st["candidates_injected_on_proved"] == 2
    assert st["candidates_used"] == 1          # comment mention excluded
    assert st["proved_goals_using_any"] == 1


def test_hint_stats_self_calibrates_to_usage_window(tmp_path: Path) -> None:
    conn = _setup(tmp_path)
    gid = _db.insert_goal(
        conn, problem=P, slug="g1",
        lean_path="Problems/Test/kstats/proofs/L_g1.lean",
        statement="T", origin="backward", status="proved")
    # Pre-telemetry Builder proved (no usage row exists yet at its time)
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at) VALUES"
        " ('old1', 'Builder', ?, 'Goal', 'succeeded', 'proved',"
        "  '2026-01-01T00:00:00', '2026-01-01T00:01:00')", (str(gid),))
    # Post-telemetry: one LLM win (has usage) + one hint win (no usage)
    for pid, fin in (("new1", "2026-06-02T00:01:00"),
                     ("new2", "2026-06-03T00:01:00")):
        conn.execute(
            "INSERT INTO pipelines (id, kind, target_id, target_kind,"
            " status, outcome, started_at, finished_at) VALUES"
            " (?, 'Builder', ?, 'Goal', 'succeeded', 'proved', ?, ?)",
            (pid, str(gid), fin, fin))
    conn.execute(
        "INSERT INTO spawn_usage (pipeline_id, kind, problem,"
        " input_tokens, output_tokens, cache_read_tokens,"
        " cache_new_tokens, turns, wall_sec, ts) VALUES"
        " ('new1', 'Builder', ?, 1, 1, 0, 0, 1, 1.0,"
        "  '2026-06-01T00:00:00')", (P,))
    conn.commit()

    hs = ks.hint_stats(conn, problem_like=P)
    # 'old1' predates the telemetry window — excluded, not a fake free win
    assert hs["builder_proved"] == 2
    assert hs["llm_spawned"] == 1
    assert hs["hint_probe_wins"] == 1
