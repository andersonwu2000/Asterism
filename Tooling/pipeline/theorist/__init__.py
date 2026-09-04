"""The Theorist pipeline — the theory layer's one wake.

Three layers (theory_wake_design.md): the THEORY layer writes the
mathematics the record does not have, the STRATEGY layer decides how
the programme runs inside the known, the FORMAL layer turns an argued
proof into Lean. This package is the first of the three, and it is
shaped like the third's relationship to the second: a `Theorize`
decision dispatches a Theorist the way an `Inject` dispatches a
Formalizer, and its product comes back as that batch's outcome.

The shape is the Strategist's wake (the real Context for a live group)
welded to the Adversary's review loop (a projection the reviewer rules
on, fired bullets back to the author on the same session, up to three
revisions) — ported from `Tooling/experiments/theory_wake.py`, where
every rule in `verdict.py` was paid for.

What is different from both, and deliberately:

  * the product is a DOCUMENT, so there is no decision.json, no
    verifier and no commit — and the landing is the Project's own shelf
    (`_docs/agent/`), not `proofs/`.
  * the Context is compiled for `trigger_kind='theory'`: the `##
    Trigger` section carries the request, and `## Programme` becomes a
    pointer, because a theory author reads the Programme by section
    when it bears on the wall rather than paying for all of it inline.
  * a run that never passes review still leaves a row. The document
    stays in the attempts dir; the request, the rounds and the last
    verdict are what the next request on that wall is written against.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from . import landing as _landing
from .review import review as review_round
from .verdict import (REPORT_BASENAME, clear_lines, parse_theory_verdict)

#: What the failure outcome says to the Strategist that asked. Fixed
#: wording (theory_wake_design.md §3.7): a rejection is not a bug
#: report, it is an instruction — the request itself is what the next
#: wake has to change.
REJECTED_DETAIL = "The Theorist's document did not pass review — reconsider your request"

#: Revision rounds a fired verdict may buy, on the SAME author session.
#: Three, from the experiment: the author that has not answered the
#: reviewer by its third revision is not one round away.
DEFAULT_ROUNDS = 3


def _rc_reason(rc: int, seat: str) -> str:
    """A spawn rc read against the SEAT that produced it. The two theory
    seats can sit on different providers, and a provider's rc contract
    is a property of the provider — reading the reviewer's rc against
    the author's declaration is how an unclassified failure gets charged
    to the wrong thing."""
    from ...llm import capabilities as _caps
    from ...state.failures import rc_to_reason
    return rc_to_reason(rc, rc_contract=_caps.for_kind(seat).rc_contract)


def _settle(conn: sqlite3.Connection, decision_id: "int | None", *,
            outcome: str, detail: str) -> None:
    """Fill the `Theorize` row's outcome and let the batch cycle run.

    Both roads settle it, and that is load-bearing: a NULL outcome is
    what "the theory layer is still working" means everywhere else in
    the framework, so a pipeline that returned without writing one
    would suppress its group's stall rescue forever and never wake it
    with the answer."""
    if decision_id is None:
        return
    from ...state import transitions as _transitions
    _transitions._record_inject_decision_outcome(
        conn, int(decision_id), outcome, "", detail=detail)
    _transitions._maybe_enqueue_inject_batch_done(conn, int(decision_id))


def _request_of(conn: sqlite3.Connection,
                decision_id: "int | None") -> "tuple[str, str]":
    """The objective and situation the decision carried."""
    if decision_id is None:
        return "", ""
    row = conn.execute(
        "SELECT payload FROM strategist_decisions WHERE id = ?",
        (int(decision_id),)).fetchone()
    if row is None:
        return "", ""
    try:
        payload = json.loads(str(row["payload"]) or "{}")
    except (TypeError, ValueError):
        return "", ""
    return (str(payload.get("objective") or ""),
            str(payload.get("situation") or ""))


def run_theorist(conn: sqlite3.Connection, *, problem: str,
                 workspace: Path, intent, pipeline_id: str,
                 group_id: "int | None" = None,
                 decision_id: "int | None" = None) -> "object":
    """Author, review, land. Returns a `PipelineResult`.

    `outcome='success'` when the document passed review and landed,
    `'failed'` on every other road — and on every road the `Theorize`
    row is settled before returning, so the group is woken with what
    came back."""
    from ... import agent
    from ...core import config
    from ...state import db
    from .. import PipelineResult, PROMPT_DIR, write_tools_mcp_config
    from ...agent.phase2_context import compile_strategist_context

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    attempts_dir.mkdir(parents=True, exist_ok=True)
    problem_dir = db.problem_dir(workspace, problem)
    objective, situation = _request_of(conn, decision_id)

    def _fail(reason: str, detail: str):
        _settle(conn, decision_id, outcome="failed",
                detail=f"{REJECTED_DETAIL}\n\n{detail}")
        return PipelineResult(outcome="failed", failure_reason=reason,
                              failure_detail=detail)

    if not objective.strip():
        # Unreachable through `verify_decision`, and that is exactly why
        # it is checked: a row hand-written into the DB would otherwise
        # spend an xhigh author turn on an empty question.
        return _fail("theory_no_request",
                     "the Theorize decision carries no objective")

    # Stage 1 — the group's own Context, under the theory request.
    compile_strategist_context(
        conn, problem=problem, trigger_kind="theory",
        attempts_dir=attempts_dir, workspace=workspace, intent=intent,
        group_id=group_id,
        theory_request={"objective": objective, "situation": situation})

    author_timeout = config.get(
        "theorist.timeout_sec", default=10800,
        env_var="ASTERISM_THEORIST_TIMEOUT_SEC", cast=int)
    rounds = max(0, config.get(
        "theorist.rounds", default=DEFAULT_ROUNDS,
        env_var="ASTERISM_THEORIST_ROUNDS", cast=int))
    tools_cfg = write_tools_mcp_config(attempts_dir, workspace,
                                       seat="theorist")
    prompt_path = PROMPT_DIR / "theorist" / "theory.md"
    report_path = attempts_dir / REPORT_BASENAME
    sid = str(uuid.uuid4())

    dialogue: "list[dict]" = []
    verdict: "dict | None" = None
    body = ""
    turn = 0
    for revision in range(0, rounds + 1):
        turn = revision + 1
        # Round 0 is the cold wake; every later round RESUMES the same
        # session carrying the fired bullets verbatim — the exact path
        # the batch wake's rebuttal rides.
        rebuttal = None
        if revision:
            rebuttal = "\n".join(
                f"- {c}" for c in (verdict or {}).get("criticisms", []))
        rc = agent.spawn_llm(
            kind="theorist", prompt_path=prompt_path,
            problem_dir=problem_dir, attempts_dir=attempts_dir,
            session_id=sid, is_retry=bool(revision),
            retry_context=rebuttal, timeout_sec=author_timeout,
            mcp_config_path=tools_cfg)
        if rc != 0:
            return _fail(_rc_reason(rc, "theorist"),
                         f"the author's spawn returned rc={rc} on round "
                         f"{turn}")
        body = (report_path.read_text(encoding="utf-8")
                if report_path.is_file() else "")
        if not body.strip():
            return _fail("theory_no_report",
                         f"the author wrote no {REPORT_BASENAME} on "
                         f"round {turn}")

        verdict, err, rrc = review_round(
            round_no=turn, attempts_dir=attempts_dir, conn=conn,
            workspace=workspace, problem=problem, group_id=group_id,
            objective=objective, situation=situation, report_body=body,
            dialogue=dialogue, pipeline_id=pipeline_id)
        if rrc != 0:
            return _fail(_rc_reason(rrc, "theory_reviewer"),
                         f"the reviewer's spawn returned rc={rrc} on "
                         f"round {turn}")
        if verdict is None:
            return _fail("theory_no_verdict",
                         f"the reviewer produced no usable verdict on "
                         f"round {turn}: {err}")
        if verdict["verdict"] == "pass":
            break
        dialogue.append({"round": turn,
                         "criticisms": verdict["criticisms"]})

    accepted = bool(verdict) and verdict.get("verdict") == "pass"
    verdict_json = json.dumps(verdict or {}, ensure_ascii=False)
    if not accepted:
        _landing.record(
            conn, problem=problem, group_id=group_id,
            pipeline_id=pipeline_id, decision_id=decision_id,
            objective=objective, situation=situation, path=None,
            status="rejected", rounds=turn, verdict_json=verdict_json)
        summary = "\n".join(f"- {c}"
                            for c in (verdict or {}).get("criticisms", []))
        return _fail(
            "theory_rejected",
            f"{turn} round(s), the reviewer's last ruling still fired:\n"
            f"{summary}")

    path = _landing.land(
        workspace, conn, problem=problem, group_id=group_id,
        pipeline_id=pipeline_id, body=body, rounds=turn,
        clear_lines=clear_lines(verdict))
    _landing.record(
        conn, problem=problem, group_id=group_id,
        pipeline_id=pipeline_id, decision_id=decision_id,
        objective=objective, situation=situation, path=path,
        status="accepted", rounds=turn, verdict_json=verdict_json)
    _settle(conn, decision_id, outcome="success", detail=path)
    print(f"[theorist] {problem} g{group_id}: accepted after {turn} "
          f"round(s) — {path}", flush=True)
    return PipelineResult(outcome="success")


__all__ = ["run_theorist", "REJECTED_DETAIL", "DEFAULT_ROUNDS",
           "parse_theory_verdict"]
