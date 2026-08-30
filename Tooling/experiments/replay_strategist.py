"""Replay ONE full Strategist wake (agent → verify → judge loop → commit)
inside a rewound scratch workspace (experiment 2, 2026-08-30).

The question: with today's prompts, seats and judge, does the
Strategist of group 504 — woken by the same `inject_batch_done` the
original rev-20 wake ran under — propose the fin10 table brick again?
Everything the wake commits (decisions, goals, the programme revision)
lands in the SCRATCH DB; the real DB is never opened.

    cd D:/Asterism_tt && python -m Tooling.experiments.replay_strategist \
        --problem Combinatorics.union_closed --group 504 \
        --since 2026-08-26T04:11:05+00:00
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--problem", required=True)
    ap.add_argument("--group", required=True, type=int)
    ap.add_argument("--since", required=True,
                    help="the rewind cutoff (ISO-8601 UTC) — the trigger derivation's "
                         "'daemon start'")
    ap.add_argument("--trigger", default=None,
                    help="force a trigger_kind instead of deriving it from the scene")
    ap.add_argument("--workspace", default=".", help="the rewound scratch workspace")
    a = ap.parse_args(argv)

    workspace = Path(a.workspace).resolve()
    os.chdir(workspace)
    sys.path.insert(0, str(workspace))
    if (workspace / "daemon.pid").exists() or (workspace / ".asterism" / "daemon.pid").exists():
        raise SystemExit("refusing: a daemon.pid sits in the workspace — replay only on a scratch copy")

    from Tooling.core.dispatcher import triggers as _triggers
    from Tooling.pipeline import strategist
    from Tooling.state import db, intent as intent_mod

    conn = db.connect(workspace / "asterism.db")
    intent = intent_mod.read(conn, a.problem)
    if intent is None:
        raise SystemExit(f"{a.problem}: no problems row in the scratch DB")
    derived, pending_id = _triggers._derive_strategist_trigger(
        conn, a.problem, group_id=a.group, routine_interval_min=120.0,
        since_iso=a.since)
    trigger = a.trigger or derived
    print(f"[replay] derived trigger={derived!r} pending_review={pending_id} "
          f"→ running as {trigger!r}", flush=True)

    t0 = datetime.now(timezone.utc).isoformat()
    pipeline_id = str(uuid.uuid4())
    db.record_pipeline_start(conn, pipeline_id=pipeline_id, kind="Strategist",
                             target_id=str(a.group), target_kind="Group")
    conn.commit()
    r = strategist.run_strategist(
        conn, problem=a.problem, trigger_kind=trigger, tick=0,
        workspace=workspace, intent=intent, pipeline_id=pipeline_id,
        pending_review_id=pending_id if trigger == "pending_review" else None,
        group_id=a.group)
    status = "succeeded" if r.outcome in ("proved", "success") else "failed"
    db.finish_pipeline(conn, pipeline_id=pipeline_id, status=status, outcome=r.outcome)
    conn.commit()

    decisions = [dict(x) for x in conn.execute(
        "SELECT id, decision_kind, target_id, produced_goal_id, substr(brief, 1, 400) AS brief,"
        " substr(reason, 1, 300) AS reason FROM strategist_decisions"
        " WHERE problem = ? AND created_at >= ? ORDER BY id", (a.problem, t0))]
    revs = [dict(x) for x in conn.execute(
        "SELECT id, rev, status, rounds, group_id, discard_reason, length(body) AS body_chars"
        " FROM programme_revisions WHERE problem = ? AND created_at >= ? ORDER BY id",
        (a.problem, t0))]
    goals = [dict(x) for x in conn.execute(
        "SELECT id, slug, status FROM goals WHERE problem = ? AND created_at >= ? ORDER BY id",
        (a.problem, t0))]
    out = {"pipeline_id": pipeline_id, "trigger": trigger, "outcome": r.outcome,
           "failure_reason": r.failure_reason, "failure_detail": r.failure_detail[:600],
           "decisions": decisions, "programme_revisions": revs, "goals_minted": goals}
    from Tooling.agent import runtime as _rt
    attempts_dir = _rt.attempts_dir_for(workspace, pipeline_id)
    attempts_dir.mkdir(parents=True, exist_ok=True)
    (attempts_dir / "replay_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if status == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())
