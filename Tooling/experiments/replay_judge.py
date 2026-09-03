"""Replay ONE Adversary round against a historical proposal, inside a
rewound scratch workspace (experiment 3, 2026-08-30).

The question: with today's judge prompt, seat and tools, does the judge
still pass the proposal that minted `fin10_nine_trace_depth_two_source_bound`
(union_closed rev 20, group 504, 2026-08-26 04:13Z)? The original judge
passed it in round 2 and named that brick as "the way out".

Inputs come from two databases: the rewound scratch DB (the scene the
judge sees — goals, groups, catalog, tree) and the untouched source DB
(the proposal body and the decisions the author filed, which the rewind
deleted because they postdate the cutoff). Nothing here writes to the
source DB; the scratch DB is the experiment's own copy.

    cd D:/Asterism_tt && python -m Tooling.experiments.replay_judge \
        --source-db D:/Asterism/asterism.db --problem Combinatorics.union_closed \
        --group 504 --rev-row 1119 --trigger inject_batch_done
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path

from . import print_json


def reconstruct_decisions(rows: "list[sqlite3.Row | dict]") -> "list[dict]":
    """`strategist_decisions` rows → the decision.json objects the
    author filed. Inject prose lives under `proof` (the parser's key),
    Delegate's under `charter`, every other kind's under `brief`;
    structured params ride flat, the way the agent writes them."""
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        kind = str(d["decision_kind"])
        obj: dict = {"kind": kind}
        if d.get("target_id") is not None:
            obj["target_id"] = int(d["target_id"])
        prose = d.get("brief")
        if prose:
            # The key the parser reads this column back out of — shared
            # with `_parse_one` and with the judge-facing renderer, so
            # a fourth contract cannot drift in behind them.
            from Tooling.pipeline.strategist.model import brief_field
            obj[brief_field(kind)] = str(prose)
        if d.get("reason"):
            obj["reason"] = str(d["reason"])
        try:
            payload = json.loads(d.get("payload") or "{}")
        except ValueError:
            payload = {}
        for k, v in (payload or {}).items():
            # framework-stamped batch bookkeeping is not author input
            if k in ("step_index", "batch_size"):
                continue
            obj[k] = v
        out.append(obj)
    return out


def load_proposal(source_db: Path, rev_row: int) -> "tuple[str, str, list[dict]]":
    """(problem, proposal body, decision objects) for one programme_revisions row."""
    conn = sqlite3.connect(f"file:{source_db.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rev = conn.execute(
            "SELECT problem, body, batch_id FROM programme_revisions WHERE id = ?",
            (int(rev_row),)).fetchone()
        if rev is None:
            raise SystemExit(f"no programme_revisions row {rev_row}")
        if not rev["batch_id"]:
            raise SystemExit(f"rev row {rev_row} carries no batch_id (discarded?) — "
                             f"nothing was filed with it")
        rows = conn.execute(
            "SELECT decision_kind, target_id, brief, reason, payload"
            " FROM strategist_decisions WHERE batch_id = ? ORDER BY id",
            (rev["batch_id"],)).fetchall()
        return str(rev["problem"]), str(rev["body"]), reconstruct_decisions(rows)
    finally:
        conn.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source-db", required=True, help="the REAL DB (read-only)")
    ap.add_argument("--problem", required=True)
    ap.add_argument("--group", required=True, type=int)
    ap.add_argument("--rev-row", required=True, type=int,
                    help="programme_revisions.id of the proposal to re-judge")
    ap.add_argument("--trigger", default="inject_batch_done",
                    help="trigger_kind the original wake ran under")
    ap.add_argument("--workspace", default=".", help="the rewound scratch workspace")
    a = ap.parse_args(argv)

    workspace = Path(a.workspace).resolve()
    os.chdir(workspace)
    sys.path.insert(0, str(workspace))
    if (workspace / "daemon.pid").exists() or (workspace / ".asterism" / "daemon.pid").exists():
        raise SystemExit("refusing: a daemon.pid sits in the workspace — replay only on a scratch copy")

    from Tooling.agent import runtime as _rt
    from Tooling.agent.phase2_context import compile_strategist_context
    from Tooling.pipeline import adversary
    from Tooling.pipeline.strategist.model import parse_decisions
    from Tooling.state import db, intent as intent_mod

    problem, body, objs = load_proposal(Path(a.source_db).resolve(), a.rev_row)
    if problem != a.problem:
        raise SystemExit(f"rev row {a.rev_row} belongs to {problem!r}, not {a.problem!r}")
    decisions, err = parse_decisions(json.dumps(objs))
    if err or decisions is None:
        raise SystemExit(f"reconstructed decisions do not parse: {err}")

    conn = db.connect(workspace / "asterism.db")
    pipeline_id = str(uuid.uuid4())
    attempts_dir = _rt.attempts_dir_for(workspace, pipeline_id)
    attempts_dir.mkdir(parents=True, exist_ok=True)
    intent = intent_mod.read(conn, problem)
    if intent is None:
        raise SystemExit(f"{problem}: no problems row in the scratch DB")
    compile_strategist_context(
        conn, problem=problem, trigger_kind=a.trigger, attempts_dir=attempts_dir,
        workspace=workspace, intent=intent, group_id=a.group)
    (attempts_dir / "proposal.md").write_text(body, encoding="utf-8")
    (attempts_dir / "decision.json").write_text(
        json.dumps(objs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[replay] scene compiled in {attempts_dir} — {len(decisions)} decision(s), "
          f"proposal {len(body)} chars; spawning the judge", flush=True)

    verdict, jerr, rc = adversary.review(
        round_no=1, attempts_dir=attempts_dir,
        problem_dir=db.problem_dir(workspace, problem), conn=conn,
        problem=problem, proposal_body=body, decisions=decisions,
        dialogue=[], proof_warn=None, group_id=a.group)
    out = {"pipeline_id": pipeline_id, "rev_row": a.rev_row, "rc": rc,
           "err": jerr, "verdict": verdict}
    (attempts_dir / "replay_verdict.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print_json(out)
    return 0 if rc == 0 and verdict is not None else 1


if __name__ == "__main__":
    sys.exit(main())
