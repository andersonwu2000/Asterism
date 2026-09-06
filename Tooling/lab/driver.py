"""`python -m Tooling.lab.driver --spec <file>` — the DRIVER: what is
actually woken inside a lab workspace.

RUNS INSIDE THE WORKSPACE, AS ITS OWN PROCESS, ON THE WORKSPACE'S OWN
CODE. That is not a style choice. `pipeline.PROMPT_DIR` is derived from
the importing module's location and `core.config` reads the cwd's
`Asterism.yaml`, so a driver running in the parent's interpreter would
read the FRAMEWORK's prompts and the OPERATOR's seats while the arm's
overlay sat unread in the workspace — the arm would look like it ran and
be a control. `lab run` therefore spawns this module with `cwd` set to
the workspace, where `-m` puts the workspace first on `sys.path`, and
`assert_workspace_code` checks that it worked rather than trusting it.

Six kinds, ported from the retired `Tooling/experiments/` runners (and,
for the last, from `.asterism/gauntlet/harness.py`) with their logic
intact and their hardcoded paths gone:

  judge_round       one Adversary round on a proposal — a historical
                    one (`replay_judge`: the scene from this
                    workspace's DB, the proposal and its filed
                    decisions from the slice's pre-rewind `source.db`),
                    or one authored as a FILE, which is what a standard
                    trap is: a scene the record never held.
  strategist_wake   one full Strategist wake — agent, verify, judge
                    loop, commit into THIS DB (`replay_strategist`).
  theory_wake       one Theorist wake through the productised pipeline
                    (`pipeline/theorist`), dispatched from a `Theorize`
                    row the driver files, exactly as a Strategist would.
  push_wake         the Strategist seat, this wake's real Context, an
                    arbitrary prompt, and no framework verdict at the
                    end (`push_wake`) — up to two turns on one session.
  daemon            the framework's own daemon in this workspace, on its
                    own gateway port, until `--once` drains or a
                    declared stop condition fires.
  gauntlet          bare force: N independent Lean bricks, proofs
                    stripped, one shot each with no tools at all
                    (`gauntlet.py` — the only kind that never opens the
                    DB).

Every kind writes `driver_result.json` and copies its attempts tree into
`_out/` whole. Whole, not by whitelist: the artefact that mattered on
2026-09-04 was a REFUSED verdict, which arm3h_r2 had unlinked, and the
shape had to be dug out of a codex rollout afterwards.

Every kind also copies `.asterism/agent_feedback.md` out
(`keep_feedback`, reported as `feedback_records`). The lab is where a
prompt change is judged by what the agents complain about, and that file
is the only place they say it — inside the runtime-state tree the run
deletes.

And every kind runs under `teardown.with_gateway_teardown`. A gateway
that outlives its daemon is the production feature; in a lab workspace,
which is discarded when the run ends, it is a 2 GB orphan holding the
directory open.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path


# ---------------------------------------------------------------------
# entering the pipeline the way the CLI enters it
# ---------------------------------------------------------------------

def harden_console() -> None:
    """Force UTF-8 console I/O, the way the CLI's own entry point does.

    A driver is an ENTRY POINT into the very pipeline `asterism run`
    enters — and the CLI calls `_force_utf8_io` before it runs anything,
    precisely because a framework print carries Lean prose (`∃`, `∉`)
    and status glyphs (`⚠`) a locale-default Windows console cannot
    spell. The retired runners skipped it, so the same
    UnicodeEncodeError arrived one layer in: arm C run 2 of the push
    experiment (2026-09-03) died at a length warning inside the wake,
    with its proposal written, its Adversary round spent and nothing
    committed.

    Deferred import: it must resolve against the workspace already on
    `sys.path`, not against whatever imported this module."""
    from Tooling.core.cli import _force_utf8_io
    _force_utf8_io()


def assert_scratch(workspace: Path) -> None:
    """Refuse any workspace a daemon owns — `daemon.pid` is the marker.

    NOT a "is this the current directory's DB" check: that is true of a
    lab workspace the moment the driver chdirs into it, and a guard that
    fires on the documented invocation teaches operators to disable it.
    The question is OWNERSHIP (a marker in the tree), not where the
    caller is standing."""
    ws = Path(workspace)
    for marker in (ws / "daemon.pid", ws / ".asterism" / "daemon.pid"):
        if marker.exists():
            raise SystemExit(
                f"refusing: {marker} exists — a daemon owns this "
                f"workspace; a driver runs only on a lab copy")


def assert_workspace_code(workspace: Path, module_file: str) -> None:
    """The `Tooling` actually imported is the WORKSPACE's.

    The arm's whole variable can be a prompt overlay, and prompts are
    read from the importing package's own directory. A driver that
    silently picked up the framework checkout's `Tooling` would run the
    unedited prompt and report the arm's name over it — the failure the
    overlay refusals in `lab build` exist to prevent, one layer down."""
    ws = Path(workspace).resolve()
    got = Path(module_file).resolve()
    try:
        got.relative_to(ws)
    except ValueError:
        raise SystemExit(
            f"refusing: this driver is running {got} — code from OUTSIDE "
            f"the workspace {ws}. The arm's prompt overlay and seat "
            f"config live in the workspace, so a run on foreign code is "
            f"a run of a different experiment. Launch with cwd set to "
            f"the workspace and no PYTHONPATH pointing at a checkout."
        ) from None


# ---------------------------------------------------------------------
# shared bookkeeping
# ---------------------------------------------------------------------

def seats_now() -> dict:
    """`kind -> {provider, model}` as THIS workspace's config has them —
    read here, inside the workspace, because that is the only process
    that can answer it. Reading a filename or the operator's own config
    is how a run gets attributed to a model it never used."""
    try:
        from Tooling.core import dispatcher
        return {k: {"provider": p, "model": m}
                for k, (p, m) in sorted(dispatcher._pipeline_seats().items())}
    except Exception as exc:            # noqa: BLE001 — a record that
        return {"_error": repr(exc)}    # cannot be taken is not a failure


def usage_for(conn, pipeline_ids: "list[str]") -> dict:
    """The provider's own token/turn accounting for this run's pipelines
    (`spawn_usage`, written per spawn by `agent.runtime`)."""
    if not pipeline_ids:
        return {}
    marks = ",".join("?" * len(pipeline_ids))
    row = conn.execute(
        f"SELECT COUNT(*) AS spawns, SUM(input_tokens) AS input_tokens,"
        f" SUM(output_tokens) AS output_tokens,"
        f" SUM(cache_read_tokens) AS cache_read_tokens,"
        f" SUM(cache_new_tokens) AS cache_new_tokens, SUM(turns) AS turns,"
        f" SUM(wall_sec) AS wall_sec FROM spawn_usage"
        f" WHERE pipeline_id IN ({marks})", pipeline_ids).fetchone()
    return {k: (row[k] if row[k] is not None else 0) for k in row.keys()}


def keep_attempts(workspace: Path, out: Path,
                  pipeline_ids: "list[str]") -> "list[str]":
    """Copy each pipeline's attempts tree into `_out/attempts/<id>/`.

    WHOLE, not by whitelist. The artefact that mattered on 2026-09-04
    was a REFUSED verdict — `theorist/review.py::keep_rejected_verdict`
    moves one aside as `verdict_r<n>_raw.json` precisely so it survives
    — and arm3h_r2 unlinked both of its, after which the shape had to be
    dug out of a codex rollout. A whitelist is a list of the artefacts
    somebody thought of before the run went wrong."""
    kept: "list[str]" = []
    for pid in pipeline_ids:
        src = Path(workspace) / ".attempts" / pid
        if not src.is_dir():
            continue
        dst = out / "attempts" / pid
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst,
                        ignore=shutil.ignore_patterns("__pycache__"))
        kept.append(f"attempts/{pid}")
    return kept


#: Where the agents' own feedback lands in `_out/`. Flat, beside
#: `driver_result.json`: it is not an attempt's artefact — every spawn
#: in the run appends to one file — and a reader looking for "what did
#: the agents say about the framework" should not have to guess which
#: pipeline id to open.
FEEDBACK_BASENAME = "agent_feedback.md"


def keep_feedback(workspace: Path, out: Path) -> "tuple[list[str], int]":
    """Copy the agents' feedback file out of the workspace, and count
    the records in it. Returns (artefact names, record count).

    THE LAB IS WHERE A PROMPT CHANGE IS JUDGED BY WHAT THE AGENTS
    COMPLAIN ABOUT, and this file is the only place they say it —
    survivor self-reports plus the framework's own death causes
    (`pipeline/_feedback.py`). It is written into `.asterism/`, which is
    runtime state, which is exactly what `lab run` deletes when the run
    ends: without this copy the first end-to-end run's four reports
    survived only because the workspace happened to still be standing
    (2026-09-07).

    Called for EVERY kind, from `main`, rather than per-kind beside
    `keep_attempts`: the daemon arm keeps no attempts tree at all
    (`run_daemon` returns no pipeline ids) and it is the arm that runs
    the most spawns. Best-effort — a run that produced a verdict must
    not fail because a copy did not."""
    try:
        from Tooling.pipeline._feedback import count_records, feedback_path
        src = feedback_path(Path(workspace))
        if not src.is_file():
            return [], 0
        dst = Path(out) / FEEDBACK_BASENAME
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        return [FEEDBACK_BASENAME], count_records(
            dst.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:            # noqa: BLE001 — see docstring
        print(f"[lab] agent feedback not kept: {type(exc).__name__}: {exc}",
              flush=True)
        return [], 0


def _intent(conn, problem: str):
    from Tooling.state import intent as intent_mod
    who = intent_mod.read(conn, problem)
    if who is None:
        raise SystemExit(f"{problem}: no problems row in this workspace's DB")
    return who


def _new_pipeline(conn, *, kind: str, target_id: str,
                  target_kind: str) -> str:
    from Tooling.state import db
    pid = str(uuid.uuid4())
    db.record_pipeline_start(conn, pipeline_id=pid, kind=kind,
                             target_id=target_id, target_kind=target_kind)
    conn.commit()
    return pid


# ---------------------------------------------------------------------
# judge_round — one Adversary round on a historical proposal
# ---------------------------------------------------------------------

def reconstruct_decisions(rows) -> "list[dict]":
    """`strategist_decisions` rows -> the decision.json objects the
    author filed. An Inject names its brick under `brick` (2026-09-07);
    a Delegate's charter lives under `charter`, every other kind's prose
    under `brief`; structured params ride flat, the way the agent writes
    them. A legacy Inject row — one filed before the named-brick ruling,
    or by a person — still carries its prose under `proof`, which is
    what that row actually was."""
    from Tooling.pipeline.strategist.model import brief_field
    out: "list[dict]" = []
    for r in rows:
        d = dict(r)
        kind = str(d["decision_kind"])
        obj: dict = {"kind": kind}
        if d.get("target_id") is not None:
            obj["target_id"] = int(d["target_id"])
        if d.get("brick_name"):
            obj["brick"] = str(d["brick_name"])
        elif d.get("brief"):
            obj[brief_field(kind)] = str(d["brief"])
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


def load_proposal(source_db: Path, rev_row: int) -> dict:
    """One `programme_revisions` row: its problem, its body, and the
    decisions the author filed with it.

    A REJECTED revision has no `batch_id` — a proposal rebutted to
    exhaustion never commits, so no decision row was ever written. That
    used to be a hard exit, which locked out exactly the family a rubric
    change most needs re-judged (66 of the live DB's rows are rejected).
    Nothing in the DB can reconstruct them: `dialogue` carries rounds of
    (proposal, criticisms, verdict) and nothing else, and reading them
    out of the proposal's PROSE would be the free-text detection the
    framework forbids. So the row loads with an EMPTY decision list and
    a note saying so; an operator who has recovered them from a
    transcript hands them in through the arm's `decisions:` file."""
    import sqlite3
    conn = sqlite3.connect(f"file:{Path(source_db).as_posix()}?mode=ro",
                           uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rev = conn.execute(
            "SELECT problem, body, batch_id FROM programme_revisions"
            " WHERE id = ?", (int(rev_row),)).fetchone()
        if rev is None:
            raise SystemExit(f"no programme_revisions row {rev_row} in "
                             f"{source_db}")
        if not rev["batch_id"]:
            return {"problem": str(rev["problem"]), "body": str(rev["body"]),
                    "decisions": [], "batch_id": None,
                    "note": (f"rev row {rev_row} carries no batch_id — it "
                             f"was never committed, so no decisions were "
                             f"filed and none are recoverable from the "
                             f"record. The judge rules on the proposal "
                             f"against an EMPTY decisions.md; a verdict "
                             f"that turns on the batch's contents is an "
                             f"artifact of this replay, not of the "
                             f"rubric. Supply them with the arm's "
                             f"`decisions:` file.")}
        # `brick_name` is v54. A source DB is a SNAPSHOT and may be
        # older than the code replaying it — which is the whole point
        # of a replay — so the column is asked for, not assumed.
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(strategist_decisions)")}
        namesel = ", brick_name" if "brick_name" in cols else ""
        rows = conn.execute(
            "SELECT decision_kind, target_id, brief, reason, payload"
            + namesel +
            " FROM strategist_decisions WHERE batch_id = ? ORDER BY id",
            (rev["batch_id"],)).fetchall()
        return {"problem": str(rev["problem"]), "body": str(rev["body"]),
                "decisions": reconstruct_decisions(rows),
                "batch_id": str(rev["batch_id"]), "note": ""}
    finally:
        conn.close()


def resolve_group(conn, problem: str, group) -> int:
    """An arm's `group:` as an id. `root` is the problem's TOP group.

    Spelled as a word rather than as the integer it happens to be
    today: a standard set names one charter, and the top group's id is
    minted by whichever `init` built the base — a number in the table
    would go stale the first time the base is rebuilt from a clean
    root, and it would go stale SILENTLY, judging the trap against
    whatever group inherited the id."""
    from Tooling.state import groups as _groups
    text = str(group).strip().lower()
    if text in ("root", "top"):
        row = _groups.top_group(conn, problem)
        if row is None:
            raise SystemExit(
                f"{problem} has no top group in this workspace — "
                f"`group: root` names the one `init` creates, so this "
                f"workspace's problem was never initialised")
        return int(row["id"])
    return int(group)


def load_file_proposal(opts: dict) -> dict:
    """A proposal authored as a FILE, with its decisions beside it.

    This is what a standard trap is: a scene the record never held.
    The defect the trap hides is the measurement, so it cannot be
    something the framework once produced — and there is therefore no
    `programme_revisions` row to replay. The projection is the same one
    either way; only where the two author-written files come from
    differs."""
    body = Path(opts["proposal"]).read_text(encoding="utf-8")
    objs: "list[dict]" = []
    if opts.get("decisions"):
        objs = json.loads(Path(opts["decisions"]).read_text(encoding="utf-8"))
    return {"body": body, "decisions": objs, "batch_id": None,
            "note": (f"proposal from {opts['proposal']}"
                     + (f", decisions from {opts['decisions']}"
                        if opts.get("decisions")
                        else " with an EMPTY decisions.md")),
            "source": {"proposal": str(opts["proposal"]),
                       "decisions": str(opts.get("decisions") or "")}}


def _judge_sources(spec: dict, opts: dict, problem: str) -> "list[dict]":
    """Every proposal this arm puts in front of the judge, in order —
    one per `rows:` entry, or the single one `proposal:` names."""
    if opts.get("proposal"):
        return [load_file_proposal(opts)]
    source_db = Path(spec["source_db"])
    override = None
    if opts.get("decisions"):
        override = json.loads(
            Path(opts["decisions"]).read_text(encoding="utf-8"))
    out: "list[dict]" = []
    for rev_row in list(opts["rows"]):
        prop = load_proposal(source_db, int(rev_row))
        if prop["problem"] != problem:
            raise SystemExit(
                f"rev row {rev_row} belongs to {prop['problem']!r}, "
                f"not {problem!r}")
        if override is not None:
            prop["decisions"] = override
            prop["note"] = (
                f"decisions supplied from {opts['decisions']}"
                + (" — the DB has none for this revision"
                   if prop["batch_id"] is None else " (override)"))
        prop["source"] = {"rev_row": int(rev_row)}
        out.append(prop)
    return out


def run_judge_round(spec: dict, ws: Path, out: Path, *, review=None) -> dict:
    from Tooling.agent import runtime as _rt
    from Tooling.agent.phase2_context import compile_strategist_context
    from Tooling.pipeline import adversary
    from Tooling.pipeline.strategist.model import parse_decisions
    from Tooling.state import db

    review = review or adversary.review
    opts = spec["options"]
    problem = spec["problem"]
    trigger = str(opts.get("trigger") or "inject_batch_done")

    conn = db.connect(ws / "asterism.db")
    who = _intent(conn, problem)
    group = resolve_group(conn, problem, opts["group"])
    rounds, pipeline_ids = [], []
    try:
        for prop in _judge_sources(spec, opts, problem):
            objs, note = prop["decisions"], prop["note"]
            if note:
                print(f"[judge_round] NOTE: {note}", flush=True)
            decisions, err = parse_decisions(json.dumps(objs))
            if err or decisions is None:
                raise SystemExit(f"decisions do not parse: {err}")

            pid = str(uuid.uuid4())
            pipeline_ids.append(pid)
            attempts = _rt.attempts_dir_for(ws, pid)
            attempts.mkdir(parents=True, exist_ok=True)
            # The author's own snapshot, compiled the way a batch wake
            # compiles it — the judge's projection copies it verbatim,
            # and a proposal may quote it.
            compile_strategist_context(
                conn, problem=problem, trigger_kind=trigger,
                attempts_dir=attempts, workspace=ws, intent=who,
                group_id=group)
            (attempts / "proposal.md").write_text(prop["body"],
                                                  encoding="utf-8")
            (attempts / "decision.json").write_text(
                json.dumps(objs, ensure_ascii=False, indent=2),
                encoding="utf-8")
            print(f"[judge_round] {prop['source']}: scene in {attempts} — "
                  f"{len(decisions)} decision(s), proposal "
                  f"{len(prop['body'])} chars; pipeline={pid}", flush=True)
            verdict, jerr, rc = review(
                round_no=1, attempts_dir=attempts,
                problem_dir=db.problem_dir(ws, problem), conn=conn,
                problem=problem, proposal_body=prop["body"],
                decisions=decisions, dialogue=[], proof_warn=None,
                group_id=group)
            row = {"source": prop["source"], "pipeline_id": pid, "rc": rc,
                   "err": jerr, "verdict": verdict,
                   "batch_id": prop["batch_id"], "decisions_note": note,
                   "rev_row": prop["source"].get("rev_row")}
            (attempts / "replay_verdict.json").write_text(
                json.dumps(row, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8")
            rounds.append(row)
        usage = usage_for(conn, pipeline_ids)
    finally:
        conn.close()
    ok = bool(rounds) and all(r["rc"] == 0 and r["verdict"] is not None
                              for r in rounds)
    return {"outcome": "success" if ok else "failed", "rounds": rounds,
            "group_id": group, "pipeline_ids": pipeline_ids, "usage": usage,
            "artefacts": keep_attempts(ws, out, pipeline_ids)}


# ---------------------------------------------------------------------
# strategist_wake — one full wake, committed into THIS DB
# ---------------------------------------------------------------------

def run_strategist_wake(spec: dict, ws: Path, out: Path) -> dict:
    from datetime import datetime, timezone

    from Tooling.core.dispatcher import triggers as _triggers
    from Tooling.pipeline import strategist
    from Tooling.state import db

    opts = spec["options"]
    problem = spec["problem"]
    # The trigger derivation's "daemon start": the rewind cutoff when
    # the slice has one, otherwise now. Reading it off the slice rather
    # than off the clock is what makes a rewound arm derive the trigger
    # the original wake ran under instead of `routine`.
    since = str(opts.get("since") or spec.get("cutoff")
                or datetime.now(timezone.utc).isoformat())

    conn = db.connect(ws / "asterism.db")
    try:
        who = _intent(conn, problem)
        group = resolve_group(conn, problem, opts["group"])
        derived, pending_id = _triggers._derive_strategist_trigger(
            conn, problem, group_id=group, routine_interval_min=120.0,
            since_iso=since)
        trigger = str(opts.get("trigger") or derived)
        print(f"[strategist_wake] derived trigger={derived!r} "
              f"pending_review={pending_id} → running as {trigger!r}",
              flush=True)
        t0 = db.now()
        pid = _new_pipeline(conn, kind="Strategist", target_id=str(group),
                            target_kind="Group")
        r = strategist.run_strategist(
            conn, problem=problem, trigger_kind=trigger, tick=0,
            workspace=ws, intent=who, pipeline_id=pid,
            pending_review_id=(pending_id if trigger == "pending_review"
                               else None),
            group_id=group)
        status = "succeeded" if r.outcome in ("proved", "success") else "failed"
        db.finish_pipeline(conn, pipeline_id=pid, status=status,
                           outcome=r.outcome)
        conn.commit()
        result = {
            "outcome": r.outcome, "failure_reason": r.failure_reason,
            "failure_detail": (r.failure_detail or "")[:600],
            "trigger": trigger, "derived_trigger": derived,
            "pipeline_ids": [pid],
            "decisions": [dict(x) for x in conn.execute(
                "SELECT id, decision_kind, target_id, produced_goal_id,"
                " substr(brief, 1, 400) AS brief,"
                " substr(reason, 1, 300) AS reason FROM strategist_decisions"
                " WHERE problem = ? AND created_at >= ? ORDER BY id",
                (problem, t0))],
            "programme_revisions": [dict(x) for x in conn.execute(
                "SELECT id, rev, status, rounds, group_id, discard_reason,"
                " length(body) AS body_chars FROM programme_revisions"
                " WHERE problem = ? AND created_at >= ? ORDER BY id",
                (problem, t0))],
            "goals_minted": [dict(x) for x in conn.execute(
                "SELECT id, slug, status FROM goals WHERE problem = ?"
                " AND created_at >= ? ORDER BY id", (problem, t0))],
            "usage": usage_for(conn, [pid]),
        }
    finally:
        conn.close()
    result["artefacts"] = keep_attempts(ws, out, result["pipeline_ids"])
    return result


# ---------------------------------------------------------------------
# theory_wake — the productised Theorist, dispatched the way a
# Strategist dispatches it
# ---------------------------------------------------------------------

def file_theorize_decision(conn, *, problem: str, group_id: "int | None",
                           objective: str, situation: str) -> int:
    """The `Theorize` row the wake answers.

    `run_theorist` reads its request out of a decision row and settles
    that row's outcome on every road — so a lab wake needs a real one,
    filed the way the Strategist files it, rather than a parameter the
    production path does not have. Anything else would be a second way
    to start a Theorist, and the one the daemon uses would go untested."""
    from Tooling.state import db
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, payload, reason,"
        " created_at, updated_at)"
        " VALUES (?, 0, 'routine', 'Theorize', ?, ?, ?, ?, ?)",
        (problem, group_id,
         json.dumps({"objective": objective, "situation": situation}),
         "filed by `asterism lab run`", ts, ts))
    conn.commit()
    return int(cur.lastrowid)


def run_theory_wake(spec: dict, ws: Path, out: Path) -> dict:
    from Tooling.pipeline import theorist
    from Tooling.state import db

    opts = spec["options"]
    problem = spec["problem"]
    req = dict(opts.get("request") or {})
    conn = db.connect(ws / "asterism.db")
    try:
        who = _intent(conn, problem)
        group = (resolve_group(conn, problem, opts["group"])
                 if opts.get("group") is not None else None)
        decision_id = file_theorize_decision(
            conn, problem=problem, group_id=group,
            objective=str(req.get("objective") or ""),
            situation=str(req.get("situation") or ""))
        pid = _new_pipeline(conn, kind="Theorist",
                            target_id=str(group if group is not None
                                          else problem),
                            target_kind="Group" if group is not None
                            else "Problem")
        r = theorist.run_theorist(
            conn, problem=problem, workspace=ws, intent=who,
            pipeline_id=pid, group_id=group, decision_id=decision_id)
        db.finish_pipeline(
            conn, pipeline_id=pid,
            status="succeeded" if r.outcome == "success" else "failed",
            outcome=r.outcome)
        conn.commit()
        docs = [dict(x) for x in conn.execute(
            "SELECT id, path, status, rounds FROM theory_documents"
            " WHERE problem = ? ORDER BY id DESC LIMIT 5", (problem,))]
        # THIS wake's document, keyed by the pipeline that wrote it —
        # the list above is context (the problem's last few), and a
        # score read off its head would grade whichever document the
        # slice happened to arrive with when the wake produced none.
        mine = [dict(x) for x in conn.execute(
            "SELECT id, path, status, rounds FROM theory_documents"
            " WHERE pipeline_id = ? ORDER BY id DESC LIMIT 1", (pid,))]
        result = {"outcome": r.outcome,
                  "failure_reason": r.failure_reason,
                  "failure_detail": (r.failure_detail or "")[:1200],
                  "decision_id": decision_id, "pipeline_ids": [pid],
                  "theory_documents": docs,
                  "theory_document": (mine[0] if mine else None),
                  "usage": usage_for(conn, [pid])}
    finally:
        conn.close()
    result["artefacts"] = keep_attempts(ws, out, [pid])
    # The landed document travels too: it is the product, and it lives
    # on the Project's shelf rather than in the attempts dir. A REFUSED
    # one lands as well (owner ruling 2026-09-06) and is exactly the
    # post-mortem material a failed arm is read for.
    for doc in docs:
        src = ws / str(doc.get("path") or "")
        if src.is_file():
            dst = out / "documents" / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            result["artefacts"].append(f"documents/{src.name}")
    return result


# ---------------------------------------------------------------------
# push_wake — the seat, the real Context, an arbitrary instruction
# ---------------------------------------------------------------------

#: What the runner keeps from the attempts dir, per turn. Turn 2
#: overwrites turn 1's note in place, so turn 1's is snapshotted before
#: the resume rather than collected at the end.
_TURN_ARTEFACTS = ("note.md", "_parser_state.json")


def _thread_id(attempts_dir: Path, session_id: str) -> "str | None":
    """The provider thread this session is filed under — present only
    once the cold turn recorded one, which is exactly the condition a
    resume needs."""
    try:
        raw = (attempts_dir / "_codex_sessions.json").read_text(
            encoding="utf-8")
        return json.loads(raw).get(session_id) or None
    except (OSError, ValueError, AttributeError):
        return None


def _snapshot_turn(attempts_dir: Path, out: Path, suffix: str) -> "list[str]":
    out.mkdir(parents=True, exist_ok=True)
    kept: "list[str]" = []
    for name in _TURN_ARTEFACTS:
        src = attempts_dir / name
        if not src.is_file():
            continue
        stem, dot, ext = name.partition(".")
        dst = out / f"{stem}{suffix}{dot}{ext}"
        shutil.copyfile(src, dst)
        kept.append(dst.name)
    return kept


def run_push_wake(spec: dict, ws: Path, out: Path) -> dict:
    from Tooling import agent
    from Tooling.agent import runtime as _rt
    from Tooling.agent.phase2_context import compile_strategist_context
    from Tooling.core import config
    from Tooling.pipeline import write_tools_mcp_config
    from Tooling.state import db

    opts = spec["options"]
    problem = spec["problem"]
    trigger = str(opts.get("trigger") or "inject_batch_done")
    prompts = [Path(opts["prompt"])]
    if opts.get("prompt2"):
        prompts.append(Path(opts["prompt2"]))

    conn = db.connect(ws / "asterism.db")
    try:
        who = _intent(conn, problem)
        group = resolve_group(conn, problem, opts["group"])
        pid = _new_pipeline(conn, kind="Strategist", target_id=str(group),
                            target_kind="Group")
        attempts = _rt.attempts_dir_for(ws, pid)
        attempts.mkdir(parents=True, exist_ok=True)
        # The wake's real materials: the same compile a batch wake runs,
        # so the companions land beside Context.md exactly as usual.
        compile_strategist_context(
            conn, problem=problem, trigger_kind=trigger,
            attempts_dir=attempts, workspace=ws, intent=who, group_id=group)
        tools_cfg = write_tools_mcp_config(attempts, ws, seat="strategist",
                                           problem=problem)
        timeout = config.get("strategist.timeout_sec", default=10800,
                             env_var="ASTERISM_STRATEGIST_TIMEOUT_SEC",
                             cast=int)
        sid = str(uuid.uuid4())
        turns: "list[dict]" = []
        for n, prompt_path in enumerate(prompts, start=1):
            # TWO TURNS, ONE SESSION: turn 2 RESUMES (the identical path
            # the in-pipeline rebuttal rounds ride), because the
            # operator's own trajectory was two pushes and the statement
            # came only after the second.
            prior = _thread_id(attempts, sid)
            t0 = time.monotonic()
            rc = agent.spawn_llm(
                kind="strategist", prompt_path=prompt_path,
                problem_dir=db.problem_dir(ws, problem),
                attempts_dir=attempts, session_id=sid, continuation=n > 1,
                timeout_sec=timeout, mcp_config_path=tools_cfg)
            note = attempts / "note.md"
            rec = {"turn": n, "prompt": prompt_path.as_posix(), "rc": rc,
                   "wall_sec": round(time.monotonic() - t0, 1),
                   "resumed": bool(prior) if n > 1 else False,
                   "thread_before": prior,
                   "note_chars": (len(note.read_text(encoding="utf-8"))
                                  if note.is_file() else 0)}
            rec["kept"] = _snapshot_turn(attempts, out, f"_turn{n}")
            turns.append(rec)
            print(f"[push_wake] turn {n}: rc={rc} "
                  f"wall={rec['wall_sec']:.0f}s note={rec['note_chars']}ch "
                  f"resumed={rec['resumed']}", flush=True)
            if rc != 0:
                print(f"[push_wake] turn {n} returned rc={rc} — stopping",
                      flush=True)
                break
        db.finish_pipeline(
            conn, pipeline_id=pid,
            status=("succeeded" if turns and turns[-1]["rc"] == 0
                    else "failed"),
            outcome="push")
        conn.commit()
        usage = usage_for(conn, [pid])
    finally:
        conn.close()
    ok = bool(turns) and all(t["rc"] == 0 for t in turns)
    return {"outcome": "success" if ok else "failed", "turns": turns,
            "session_id": sid, "pipeline_ids": [pid], "usage": usage,
            "artefacts": keep_attempts(ws, out, [pid])}


# ---------------------------------------------------------------------
# daemon — the framework's own loop, in this workspace, on its own port
# ---------------------------------------------------------------------

def free_port() -> int:
    """A port nobody is on. The lab daemon must never bind the live
    workspace's 8765: two gateways on one port is one gateway serving
    two boards' Lean, and the loser dies at boot."""
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
    finally:
        s.close()


def baseline_counts(conn, problem: str) -> dict:
    return {
        "proved": int(conn.execute(
            "SELECT COUNT(*) FROM goals WHERE problem = ?"
            " AND status = 'proved'", (problem,)).fetchone()[0]),
        "revisions": int(conn.execute(
            "SELECT COUNT(*) FROM programme_revisions WHERE problem = ?"
            " AND status = 'passed'", (problem,)).fetchone()[0]),
    }


def root_proved(conn, problem: str) -> bool:
    """Did the scope problem's ROOT goal end 'proved'?

    An absolute end-state, not a delta like `baseline_counts`: the root
    is the one goal a run either lands or does not, and counting sub-goals
    cannot answer it. An end-to-end smoke item scored on `proved_at_least`
    alone passed a run whose two sub-goals proved and whose root never
    flipped, because the promotion gate's answer was dropped
    (Lab.even_sum_subsets, 2026-09-07)."""
    row = conn.execute(
        "SELECT status FROM goals WHERE problem = ? AND origin = 'root'"
        " ORDER BY id LIMIT 1", (problem,)).fetchone()
    return row is not None and str(row[0]) == "proved"


def stop_reached(conn, problem: str, stop: dict, *, baseline: dict,
                 elapsed: float) -> "str | None":
    """Which declared condition has fired, or None.

    `proved:` and `revisions:` count what this RUN produced, not what
    the workspace holds: the slice arrives with the problem's whole
    history in it, so an absolute threshold would be satisfied before
    the daemon started."""
    if not stop:
        return None
    if stop.get("wall_sec") and elapsed >= float(stop["wall_sec"]):
        return f"wall_sec>={stop['wall_sec']}"
    now = baseline_counts(conn, problem)
    for key in ("proved", "revisions"):
        want = stop.get(key)
        if want and (now[key] - baseline[key]) >= int(want):
            return f"{key}+{want}"
    return None


#: How often the stop conditions are asked. The daemon's own tick is
#: minutes long; a tighter poll would only spend the DB's read lock.
POLL_SEC = 5.0


def run_daemon(spec: dict, ws: Path, out: Path) -> dict:
    from Tooling.state import db

    opts = spec["options"]
    problem = spec["problem"]
    scope = str(opts.get("scope") or problem)
    stop = dict(opts.get("stop") or {})
    # `--once` unless a stop condition says otherwise: a lab daemon that
    # neither drains nor has a condition is one nobody stops.
    once = bool(opts.get("once", not stop))
    port = free_port()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8",
           "ASTERISM_GATEWAY_PORT": str(port)}
    cmd = [sys.executable, "-m", "Tooling.core.cli", "run", "--scope", scope]
    if once:
        cmd.append("--once")
    log_path = out / "daemon.log"
    out.mkdir(parents=True, exist_ok=True)
    conn = db.connect(ws / "asterism.db")
    base = baseline_counts(conn, problem)
    started_at = db.now()
    t0 = time.monotonic()
    fired = None
    print(f"[daemon] {' '.join(cmd)} (gateway port {port}) → {log_path}",
          flush=True)
    with open(log_path, "w", encoding="utf-8", buffering=1) as log:
        proc = subprocess.Popen(cmd, cwd=str(ws), env=env, stdout=log,
                                stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL)
        try:
            while True:
                try:
                    rc = proc.wait(timeout=POLL_SEC)
                    break
                except subprocess.TimeoutExpired:
                    pass
                fired = stop_reached(conn, problem, stop, baseline=base,
                                     elapsed=time.monotonic() - t0)
                if fired:
                    print(f"[daemon] stop condition {fired} — asking the "
                          f"daemon to finish in-flight work and exit",
                          flush=True)
                    rc = stop_and_wait(ws, proc)
                    break
        finally:
            if proc.poll() is None:
                proc.kill()
    try:
        after = baseline_counts(conn, problem)
        rooted = root_proved(conn, problem)
        usage = _usage_since(conn, t0_iso=started_at)
    finally:
        conn.close()
    return {"outcome": "success" if rc == 0 else "failed", "rc": rc,
            "gateway_port": port, "scope": scope, "once": once,
            "stop_fired": fired, "baseline": base, "after": after,
            "produced": {k: after[k] - base[k] for k in base},
            "root_proved": rooted,
            "usage": usage, "pipeline_ids": [],
            "artefacts": ["daemon.log"]}


def _usage_since(conn, *, t0_iso: str) -> dict:
    """Every spawn this run paid for — the daemon mints its own pipeline
    ids, so the usage is bounded by time rather than by a list this
    process holds."""
    row = conn.execute(
        "SELECT COUNT(*) AS spawns, SUM(input_tokens) AS input_tokens,"
        " SUM(output_tokens) AS output_tokens,"
        " SUM(cache_read_tokens) AS cache_read_tokens,"
        " SUM(cache_new_tokens) AS cache_new_tokens, SUM(turns) AS turns,"
        " SUM(wall_sec) AS wall_sec FROM spawn_usage WHERE ts >= ?",
        (t0_iso,)).fetchone()
    return {k: (row[k] if row[k] is not None else 0) for k in row.keys()}


#: How long a stop condition waits for the daemon to drain. The tick
#: loop stops spawning at once and then waits out whatever is in flight,
#: and an in-flight Strategist wake is legitimately tens of minutes.
STOP_GRACE_SEC = 1800.0
#: And how long `terminate` gets before the kill.
STOP_HARD_SEC = 30.0


def _request_graceful_stop(ws: Path) -> None:
    """`daemon stop` — the marker the tick loop reads. It stops spawning,
    drains what is in flight and exits, which is what leaves the DB
    describing a run that ENDED rather than one that was cut."""
    from Tooling.core.cli.run import daemon_stop
    daemon_stop(Path(ws), force=False)


def stop_and_wait(ws: Path, proc, *, grace_sec: float = STOP_GRACE_SEC,
                  hard_sec: float = STOP_HARD_SEC,
                  request_stop=None) -> int:
    """Ask the daemon to stop, then make sure it did.

    Graceful FIRST, always. But the wait is bounded and escalates: a
    daemon that does not take the marker — wedged mid-spawn, or holding
    a lock the stop path did not recognise — would otherwise hang the
    lab run forever on a `proc.wait()` with no timeout, which is a
    stalled experiment that looks exactly like a long one."""
    try:
        (request_stop or _request_graceful_stop)(ws)
    except Exception as exc:            # noqa: BLE001 — the escalation
        print(f"[daemon] graceful stop unavailable ({exc!r})", flush=True)
    for step, budget in (("terminate", grace_sec), ("kill", hard_sec)):
        try:
            return proc.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            print(f"[daemon] still running after {budget:.0f}s — {step}",
                  flush=True)
            getattr(proc, step)()
    return proc.wait()


# ---------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------

def run_gauntlet(spec: dict, ws: Path, out: Path) -> dict:
    """Bare force: the bricks under `items_dir`, one shot each. The
    harness itself is `Tooling/lab/gauntlet.py` — it is the only kind
    that never touches the DB, so it does not belong beside the four
    that do."""
    from Tooling.lab import gauntlet
    return gauntlet.run(Path(spec["options"]["items_dir"]), ws, out,
                        problem=spec["problem"])


KINDS = {
    "judge_round": run_judge_round,
    "strategist_wake": run_strategist_wake,
    "theory_wake": run_theory_wake,
    "push_wake": run_push_wake,
    "daemon": run_daemon,
    "gauntlet": run_gauntlet,
}

# Registered, not written here (`lab/continuity.py`): the continuity
# kinds call the SAME round functions the kinds above do, differing only
# in whose provider session the round's cold spawn lands on.
from .continuity import KINDS as _CONTINUITY_KINDS  # noqa: E402

KINDS.update(_CONTINUITY_KINDS)

RESULT_BASENAME = "driver_result.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--spec", required=True,
                    help="the JSON `lab run` wrote for this rep")
    a = ap.parse_args(argv)
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))

    ws = Path(spec["workspace"]).resolve()
    assert_scratch(ws)
    os.chdir(ws)
    sys.path.insert(0, str(ws))
    harden_console()
    import Tooling
    assert_workspace_code(ws, Tooling.__file__)

    out = Path(spec["out"]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    kind = str(spec["kind"])
    if kind not in KINDS:
        raise SystemExit(f"unknown driver kind {kind!r} — have "
                         f"{sorted(KINDS)}")
    # Deferred like every other framework import here: it must resolve
    # against the workspace already on `sys.path`.
    from Tooling.lab.teardown import with_gateway_teardown
    t0 = time.monotonic()
    result = with_gateway_teardown(KINDS[kind], spec, ws, out)
    # After the kind, before the record: the feedback file is appended
    # to by every spawn the run made, so it is only whole once they are
    # all done — and it must be out of `.asterism/` before `lab run`
    # clears the workspace.
    fb_kept, fb_n = keep_feedback(ws, out)
    result.update({"kind": kind, "problem": spec["problem"],
                   "wall_sec": round(time.monotonic() - t0, 1),
                   "seats": seats_now(),
                   "artefacts": list(result.get("artefacts") or []) + fb_kept,
                   "feedback_records": fb_n})
    (out / RESULT_BASENAME).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    print(f"[lab] {kind}: outcome={result.get('outcome')} "
          f"wall={result['wall_sec']:.0f}s", flush=True)
    return 0 if result.get("outcome") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
