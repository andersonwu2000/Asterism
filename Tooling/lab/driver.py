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

Five kinds, ported from the retired `Tooling/experiments/` runners with
their logic intact and their hardcoded paths gone:

  judge_round       one Adversary round on a historical proposal
                    (`replay_judge`): the scene from this workspace's
                    DB, the proposal and its filed decisions from the
                    slice's pre-rewind `source.db`.
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

Every kind writes `driver_result.json` and copies its attempts tree into
`_out/` whole. Whole, not by whitelist: the artefact that mattered on
2026-09-04 was a REFUSED verdict, which arm3h_r2 had unlinked, and the
shape had to be dug out of a codex rollout afterwards.
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
    author filed. Inject prose lives under `proof` (the parser's key),
    Delegate's under `charter`, every other kind's under `brief`;
    structured params ride flat, the way the agent writes them."""
    from Tooling.pipeline.strategist.model import brief_field
    out: "list[dict]" = []
    for r in rows:
        d = dict(r)
        kind = str(d["decision_kind"])
        obj: dict = {"kind": kind}
        if d.get("target_id") is not None:
            obj["target_id"] = int(d["target_id"])
        if d.get("brief"):
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
        rows = conn.execute(
            "SELECT decision_kind, target_id, brief, reason, payload"
            " FROM strategist_decisions WHERE batch_id = ? ORDER BY id",
            (rev["batch_id"],)).fetchall()
        return {"problem": str(rev["problem"]), "body": str(rev["body"]),
                "decisions": reconstruct_decisions(rows),
                "batch_id": str(rev["batch_id"]), "note": ""}
    finally:
        conn.close()


def run_judge_round(spec: dict, ws: Path, out: Path) -> dict:
    from Tooling.agent import runtime as _rt
    from Tooling.agent.phase2_context import compile_strategist_context
    from Tooling.pipeline import adversary
    from Tooling.pipeline.strategist.model import parse_decisions
    from Tooling.state import db

    opts = spec["options"]
    problem, group = spec["problem"], int(opts["group"])
    trigger = str(opts.get("trigger") or "inject_batch_done")
    source_db = Path(spec["source_db"])
    override = None
    if opts.get("decisions"):
        override = json.loads(
            Path(opts["decisions"]).read_text(encoding="utf-8"))

    conn = db.connect(ws / "asterism.db")
    who = _intent(conn, problem)
    rounds, pipeline_ids = [], []
    try:
        for rev_row in list(opts["rows"]):
            prop = load_proposal(source_db, int(rev_row))
            if prop["problem"] != problem:
                raise SystemExit(
                    f"rev row {rev_row} belongs to {prop['problem']!r}, "
                    f"not {problem!r}")
            objs, note = prop["decisions"], prop["note"]
            if override is not None:
                objs = override
                note = (f"decisions supplied from {opts['decisions']}"
                        + (" — the DB has none for this revision"
                           if prop["batch_id"] is None else " (override)"))
            if note:
                print(f"[judge_round] NOTE: {note}", flush=True)
            decisions, err = parse_decisions(json.dumps(objs))
            if err or decisions is None:
                raise SystemExit(
                    f"reconstructed decisions do not parse: {err}")

            pid = str(uuid.uuid4())
            pipeline_ids.append(pid)
            attempts = _rt.attempts_dir_for(ws, pid)
            attempts.mkdir(parents=True, exist_ok=True)
            compile_strategist_context(
                conn, problem=problem, trigger_kind=trigger,
                attempts_dir=attempts, workspace=ws, intent=who,
                group_id=group)
            (attempts / "proposal.md").write_text(prop["body"],
                                                  encoding="utf-8")
            (attempts / "decision.json").write_text(
                json.dumps(objs, ensure_ascii=False, indent=2),
                encoding="utf-8")
            print(f"[judge_round] rev {rev_row}: scene in {attempts} — "
                  f"{len(decisions)} decision(s), proposal "
                  f"{len(prop['body'])} chars; pipeline={pid}", flush=True)
            verdict, jerr, rc = adversary.review(
                round_no=1, attempts_dir=attempts,
                problem_dir=db.problem_dir(ws, problem), conn=conn,
                problem=problem, proposal_body=prop["body"],
                decisions=decisions, dialogue=[], proof_warn=None,
                group_id=group)
            row = {"rev_row": int(rev_row), "pipeline_id": pid, "rc": rc,
                   "err": jerr, "verdict": verdict,
                   "batch_id": prop["batch_id"], "decisions_note": note}
            (attempts / "replay_verdict.json").write_text(
                json.dumps(row, ensure_ascii=False, indent=2),
                encoding="utf-8")
            rounds.append(row)
        usage = usage_for(conn, pipeline_ids)
    finally:
        conn.close()
    ok = bool(rounds) and all(r["rc"] == 0 and r["verdict"] is not None
                              for r in rounds)
    return {"outcome": "success" if ok else "failed", "rounds": rounds,
            "pipeline_ids": pipeline_ids, "usage": usage,
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
    problem, group = spec["problem"], int(opts["group"])
    # The trigger derivation's "daemon start": the rewind cutoff when
    # the slice has one, otherwise now. Reading it off the slice rather
    # than off the clock is what makes a rewound arm derive the trigger
    # the original wake ran under instead of `routine`.
    since = str(opts.get("since") or spec.get("cutoff")
                or datetime.now(timezone.utc).isoformat())

    conn = db.connect(ws / "asterism.db")
    try:
        who = _intent(conn, problem)
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
    group = int(opts["group"]) if opts.get("group") is not None else None
    req = dict(opts.get("request") or {})
    conn = db.connect(ws / "asterism.db")
    try:
        who = _intent(conn, problem)
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
        result = {"outcome": r.outcome,
                  "failure_reason": r.failure_reason,
                  "failure_detail": (r.failure_detail or "")[:1200],
                  "decision_id": decision_id, "pipeline_ids": [pid],
                  "theory_documents": docs,
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
    problem, group = spec["problem"], int(opts["group"])
    trigger = str(opts.get("trigger") or "inject_batch_done")
    prompts = [Path(opts["prompt"])]
    if opts.get("prompt2"):
        prompts.append(Path(opts["prompt2"]))

    conn = db.connect(ws / "asterism.db")
    try:
        who = _intent(conn, problem)
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
        usage = _usage_since(conn, t0_iso=started_at)
    finally:
        conn.close()
    return {"outcome": "success" if rc == 0 else "failed", "rc": rc,
            "gateway_port": port, "scope": scope, "once": once,
            "stop_fired": fired, "baseline": base, "after": after,
            "produced": {k: after[k] - base[k] for k in base},
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

KINDS = {
    "judge_round": run_judge_round,
    "strategist_wake": run_strategist_wake,
    "theory_wake": run_theory_wake,
    "push_wake": run_push_wake,
    "daemon": run_daemon,
}

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
    t0 = time.monotonic()
    result = KINDS[kind](spec, ws, out)
    result.update({"kind": kind, "problem": spec["problem"],
                   "wall_sec": round(time.monotonic() - t0, 1),
                   "seats": seats_now()})
    (out / RESULT_BASENAME).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    print(f"[lab] {kind}: outcome={result.get('outcome')} "
          f"wall={result['wall_sec']:.0f}s", flush=True)
    return 0 if result.get("outcome") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
