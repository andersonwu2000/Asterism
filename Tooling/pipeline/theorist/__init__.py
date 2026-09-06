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
  * a run that never passes review lands ANYWAY (owner ruling
    2026-09-06). The row, and the document beside it under the same
    shelf: what was tried on that wall and why it failed is what the
    next request there is written against, and its header carries the
    refusal so nothing reads it as an accepted result. Whether its
    theorems may be CITED is decided by the reviewer's criterion 2
    (Rigour), not by the status — see `landing`.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from . import checkpoint as _checkpoint
from . import landing as _landing
from .review import projection_dir, review as review_round
from .verdict import (REPORT_BASENAME, RIGOUR_DEFECTIVE, fired_criteria,
                      parse_theory_verdict, rigour_is_defective)

#: What the failure outcome says to the Strategist that asked. Fixed
#: wording (theory_wake_design.md §3.7): a rejection is not a bug
#: report, it is an instruction — the request itself is what the next
#: wake has to change. RESERVED for a real ruling that fired. The
#: landed path and the criteria that fired ride BELOW it, so the wake
#: can read the document it is being told to write a better request
#: against (owner ruling 2026-09-06).
REJECTED_DETAIL = "The Theorist's document did not pass review — reconsider your request"

#: The OTHER road, and it is not that one. A wake that never came back
#: reviewed nothing, so the request is untouched — telling the
#: Strategist to reconsider it sends it to rewrite a question nobody
#: answered. union_closed g691, 2026-09-05: two Theorist runs died when
#: the codex stream hit its idle timeout on a long silent reasoning
#: turn, and both were reported as "did not pass review". The headline
#: has to name the move that is actually available.
SPAWN_DIED_DETAIL = ("The Theorist's spawn did not complete ({reason}); "
                     "the request stands — re-issue it")

#: The third road: the request itself is unusable. Nothing ran, and
#: there is nothing to re-issue either — the decision has to change.
NO_REQUEST_DETAIL = "The Theorize decision carried no usable request"

#: Revision rounds a fired verdict may buy, on the SAME author session.
#: Three, from the experiment: the author that has not answered the
#: reviewer by its third revision is not one round away.
DEFAULT_ROUNDS = 3

#: Times the framework re-issues ONE request after an infra death before
#: it settles with `SPAWN_DIED_DETAIL`. An infra cause is the
#: framework's own fault and says nothing about the request, so the
#: machine re-queues rather than hand it back (owner ruling 2026-09-06)
#: — bounded here so a provider broken for good still reaches a person
#: instead of looping. `cascade_one` owns the count.
INFRA_REDISPATCHES = 3


def _rc_reason(rc: int, seat: str, spawn_dir: "Path | None" = None) -> str:
    """A dead spawn named from the SEAT that produced it and the STDERR
    it left — in that order, stderr first.

    The seat half: the two theory seats can sit on different providers,
    and a provider's rc contract is a property of the provider, so
    reading the reviewer's rc against the author's declaration is how an
    unclassified failure gets charged to the wrong thing.

    THE STDERR HALF IS NOT COSMETIC. `pipeline._spawn_failure` has read
    transport prose ahead of the rc since 2026-08-18 and every other
    pipeline goes through it; this one grew its own rc-only classifier
    and so could never say `provider_network`. The difference is what
    the dispatcher does next: a named network failure makes it probe
    connectivity and PARK, while `unclassified_spawn_failure` feeds the
    consecutive breaker that exits the daemon rc=2 needing an operator
    on site (the 08-17 outage, twelve rows). union_closed g691 filed two
    `idle timeout waiting for websocket` deaths on 2026-09-05 with the
    cause spelled out in a file nobody read.

    `spawn_dir` is where THAT seat ran: the attempts dir for the author,
    the round's projection for the reviewer. Duration is not available
    here, so `_spawn_failure`'s fast-fail heuristic has no counterpart —
    the rc residue stays the fallback."""
    from ...llm import capabilities as _caps
    from ...state import failures as _failures
    tail = ""
    if spawn_dir is not None:
        f = spawn_dir / "_spawn.stderr"
        try:
            tail = f.read_text(encoding="utf-8")[:600] if f.is_file() else ""
        except OSError:
            tail = ""
    if _failures.is_network_failure(tail):
        return "provider_network"
    if _failures.is_local_overload_failure(tail):
        return "local_overload"
    return _failures.rc_to_reason(
        rc, rc_contract=_caps.for_kind(seat).rc_contract)


def _settle(conn: sqlite3.Connection, decision_id: "int | None", *,
            outcome: str, detail: str, failure_reason: str = "") -> None:
    """Fill the `Theorize` row's outcome and let the batch cycle run.

    Both roads settle it, and that is load-bearing: a NULL outcome is
    what "the theory layer is still working" means everywhere else in
    the framework, so a pipeline that returned without writing one
    would suppress its group's stall rescue forever and never wake it
    with the answer.

    `failure_reason` rides the enum as `failed:<reason>` — the same
    vocabulary `failed:dead` / `failed:stalled` / `failed:group_retired`
    already use for an Inject and for a spent theory request. A bare
    `failed` was what let a transport death and a fired ruling render
    identically on every surface that reads the column."""
    if decision_id is None:
        return
    from ...state import transitions as _transitions
    _transitions._record_inject_decision_outcome(
        conn, int(decision_id), outcome, failure_reason, detail=detail)
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
    from ...llm import capabilities as _caps
    from ...llm.base import SpawnRC
    from ...state import db, failures as _failures
    from .. import PipelineResult, PROMPT_DIR, write_tools_mcp_config
    from ...agent.phase2_context import compile_strategist_context

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    attempts_dir.mkdir(parents=True, exist_ok=True)
    problem_dir = db.problem_dir(workspace, problem)
    objective, situation = _request_of(conn, decision_id)

    def _fail(reason: str, detail: str, *, headline: str):
        # `headline` is required, per road: the caller that adds a
        # seventh failure must say WHICH of the three answers the
        # Strategist gets, rather than inheriting whichever one happened
        # to be the default.
        _settle(conn, decision_id, outcome="failed", failure_reason=reason,
                detail=f"{headline}\n\n{detail}")
        return PipelineResult(outcome="failed", failure_reason=reason,
                              failure_detail=detail)

    def _fail_spawn(reason: str, detail: str):
        """A wake that did not come back: nothing was reviewed.

        An INFRA reason is the framework's own fault, so the row is left
        UNSETTLED and the request is re-queued (owner ruling
        2026-09-06); `cascade_one`'s Theorist arm holds the count and
        writes this same headline once the re-issues are spent."""
        if (_failures.is_infra(reason) and decision_id is not None
                and db.decision_infra_deaths(conn, int(decision_id))
                < INFRA_REDISPATCHES):
            return PipelineResult(outcome="failed", failure_reason=reason,
                                  failure_detail=detail)
        return _fail(reason, detail,
                     headline=SPAWN_DIED_DETAIL.format(reason=reason))

    if not objective.strip():
        # Unreachable through `verify_decision`, and that is exactly why
        # it is checked: a row hand-written into the DB would otherwise
        # spend an xhigh author turn on an empty question.
        return _fail("theory_no_request",
                     "the Theorize decision carries no objective",
                     headline=NO_REQUEST_DETAIL)

    # Stage 0 — a request that has been worked on before is picked up
    # where it stopped, not started again. The dir this adopts is copied
    # in first, so every stage below reads the standard layout.
    resumed = _checkpoint.adopt(workspace, attempts_dir,
                                decision_id=decision_id,
                                pipeline_id=pipeline_id)

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
                                       seat="theorist", problem=problem)
    prompt_path = PROMPT_DIR / "theorist" / "theory.md"
    report_path = attempts_dir / REPORT_BASENAME
    sid = str(uuid.uuid4())

    # The resume point, rewritten at every state change below. Its cost
    # is one small file per transition; the cost of NOT having it was
    # measured on 2026-09-06 as a 223k-token re-authoring of a document
    # that was already written (see `checkpoint`).
    started_at = resumed.started_at if resumed else db.now()

    def _mark(phase: str, round_no: int, reviewed_body: str = "") -> None:
        _checkpoint.write(
            attempts_dir, decision_id=decision_id, group_id=group_id,
            problem=problem, author_sid=sid,
            provider=_caps.provider_for_kind("theorist", workspace),
            model=_caps.model_for_kind("theorist", workspace),
            phase=phase, round_no=round_no, started_at=started_at,
            reviewed_sha=(_checkpoint.digest(reviewed_body)
                          if reviewed_body else ""),
            resumed_from=(resumed.source_pipeline_id if resumed else ""))

    # Quota-park budget for this run, on the Strategist wake's terms: the
    # queue row's lease is reclaimed on AGE ALONE at LEASE_TTL_SEC even
    # with this thread alive, and a reclaimed row means a second Theorist
    # on the same request.
    _t0 = time.monotonic()

    def _quota_park(label: str) -> bool:
        from ...core import quota_wait as _qw
        from ...core.dispatcher import LEASE_TTL_SEC
        return _qw.park_in_pipeline(
            f"{problem} {label}",
            budget_sec=(LEASE_TTL_SEC * 0.8) - (time.monotonic() - _t0))

    dialogue: "list[dict]" = []
    verdict: "dict | None" = None
    body = ""
    reviewed = ""   # the document the reviewer has already been handed
    turn = 0
    # Where the loop starts, and what it may skip. The ROUND CAP is the
    # request's, not each process's: a run resumed at round 3 has one
    # author turn left, not four.
    first_revision = 0
    submitted = False      # the resumed round's document is already in
    author_prompt = prompt_path
    resume_cold = False    # a revision turn that cannot inherit a session

    if resumed is not None:
        print(f"[theorist] {problem} g{group_id}: resuming "
              f"{resumed.source_pipeline_id} at {resumed.phase} "
              f"round {resumed.round_no}", flush=True)
        body = _checkpoint.report_body(attempts_dir)
        dialogue = _checkpoint.dialogue_upto(attempts_dir, resumed.round_no)
        # Set even when the loop below runs: a cap LOWERED since the
        # frozen run leaves it with nothing to do, and the document
        # still has to land under the round count it actually reached.
        turn = resumed.round_no
        if resumed.phase == _checkpoint.PHASE_LANDING:
            verdict = _checkpoint.verdict_at(attempts_dir, turn)
            first_revision = rounds + 1          # the rounds are over
        elif resumed.phase == _checkpoint.PHASE_AWAITING_REVISION:
            # The reviewer ruled and the author never answered: this run
            # takes that revision turn.
            first_revision = resumed.round_no
            verdict = _checkpoint.verdict_at(attempts_dir, resumed.round_no)
            reviewed = body
            sid, author_prompt, resume_cold = _checkpoint.hand_to_author(
                attempts_dir, resumed, base_prompt=prompt_path,
                verdict=verdict, dialogue=dialogue, cold_sid=sid,
                label=f"{problem} g{group_id}")
        else:
            # `awaiting_review`, and `authoring` with a document on disk
            # resolved to it: round k's submission stands, so the next
            # thing owed is its REVIEW. This is the incident's own road.
            first_revision = resumed.round_no - 1
            submitted = bool(body.strip())

    for revision in range(first_revision, rounds + 1):
        turn = revision + 1
        # Round 0 is the cold wake; every later round RESUMES the same
        # session carrying the fired bullets verbatim — the exact path
        # the batch wake's rebuttal rides.
        rebuttal = None
        if revision:
            rebuttal = "\n".join(
                f"- {c}" for c in (verdict or {}).get("criticisms", []))
        if submitted:
            # The document for THIS round was written by the process
            # that died; re-authoring it is what this whole mechanism
            # exists to stop. Straight to the review it was waiting for.
            submitted = False
        else:
            _mark(_checkpoint.PHASE_AUTHORING, turn, reviewed)
            is_retry = bool(revision) and not resume_cold
            rc = agent.spawn_llm(
                kind="theorist", prompt_path=author_prompt,
                problem_dir=problem_dir, attempts_dir=attempts_dir,
                session_id=sid, is_retry=is_retry,
                retry_context=rebuttal if is_retry else None,
                timeout_sec=author_timeout, mcp_config_path=tools_cfg)
            if (rc == SpawnRC.STALE_SESSION and is_retry
                    and resumed is not None
                    and revision == first_revision):
                # The provider will not replay that id after all. The
                # document and the ruling are both on disk, so this
                # costs a worse turn, not the run — `author_prompt`
                # already carries them (`checkpoint.resume_prompt`).
                print(f"[theorist] {problem} g{group_id}: the author's "
                      f"session {sid} is gone (rc={rc}) — retrying cold "
                      f"with the document and the ruling in the prompt",
                      flush=True)
                sid = str(uuid.uuid4())
                _mark(_checkpoint.PHASE_AUTHORING, turn, reviewed)
                rc = agent.spawn_llm(
                    kind="theorist", prompt_path=author_prompt,
                    problem_dir=problem_dir, attempts_dir=attempts_dir,
                    session_id=sid, is_retry=False, retry_context=None,
                    timeout_sec=author_timeout, mcp_config_path=tools_cfg)
            author_prompt = prompt_path  # only the resumed turn is briefed
            resume_cold = False
            body = (report_path.read_text(encoding="utf-8")
                    if report_path.is_file() else "")
            if rc != 0:
                # THE DOCUMENT OUTRANKS THE RC. codex's stream died on
                # its idle timeout AFTER `write_file` had landed
                # report.md (union_closed g691, 2026-09-05, twice): an rc
                # says the TRANSPORT failed, and only the reviewer can
                # say whether what is on disk is any good. So a dead
                # spawn with a document goes to review exactly as if it
                # had exited 0. Salvage only what is NEW: a revision turn
                # that died before touching the file leaves the PREVIOUS
                # round's document, and re-reviewing that spends a
                # reviewer on a turn that never happened.
                if not body.strip() or body == reviewed:
                    return _fail_spawn(
                        _rc_reason(rc, "theorist", attempts_dir),
                        f"the author's spawn returned rc={rc} on round "
                        f"{turn}" + (" without rewriting the document"
                                     if body.strip() else ""))
                print(f"[theorist] {problem} g{group_id}: the author's "
                      f"spawn died (rc={rc}) on round {turn} AFTER "
                      f"writing {REPORT_BASENAME} — reviewing what it "
                      f"wrote", flush=True)
            if not body.strip():
                return _fail_spawn(
                    "theory_no_report",
                    f"the author wrote no {REPORT_BASENAME} on round "
                    f"{turn}")

        # The document is final for this round. Written BEFORE the
        # reviewer runs, because the state a reviewer's death has to
        # leave behind is exactly this one — the incident's whole cost
        # was a re-dispatch that read `authoring` here.
        _mark(_checkpoint.PHASE_AWAITING_REVIEW, turn, body)
        reviewed = body
        verdict, err, rrc = review_round(
            round_no=turn, attempts_dir=attempts_dir, conn=conn,
            workspace=workspace, problem=problem, group_id=group_id,
            objective=objective, situation=situation, report_body=body,
            dialogue=dialogue, pipeline_id=pipeline_id,
            quota_park=_quota_park)
        if rrc != 0:
            return _fail_spawn(
                _rc_reason(rrc, "theory_reviewer",
                           projection_dir(attempts_dir, turn)),
                f"the reviewer's spawn returned rc={rrc} on round {turn}")
        if verdict is None:
            return _fail_spawn(
                "theory_no_verdict",
                f"the reviewer produced no usable verdict on round "
                f"{turn}: {err}")
        if verdict["verdict"] == "pass":
            break
        dialogue.append({"round": turn,
                         "criticisms": verdict["criticisms"]})
        if revision < rounds:
            # A revision is owed. Past the cap none is, and the phase
            # there is `landing`, not a wait for a turn nobody will take.
            _mark(_checkpoint.PHASE_AWAITING_REVISION, turn, body)

    if not body.strip():
        # Only reachable on a resume whose `report.md` did not survive
        # with it: there is no document to land and nobody refused one.
        return _fail_spawn(
            "theory_no_report",
            f"the resumed run carries no {REPORT_BASENAME}")
    _mark(_checkpoint.PHASE_LANDING, turn, body)
    accepted = bool(verdict) and verdict.get("verdict") == "pass"
    verdict_json = json.dumps(verdict or {}, ensure_ascii=False)
    status = (_landing.STATUS_ACCEPTED if accepted
              else _landing.STATUS_REJECTED)
    # BOTH roads land (owner ruling 2026-09-06). A refused document is
    # the record of what was tried on this wall and why it failed —
    # post-mortem material the next request is written against — and it
    # used to survive only inside a `dead_attempts` artifacts blob,
    # which is a record nobody reads. The header and the filename carry
    # the refusal, so nothing on the shelf reads as an accepted result.
    path = _landing.land(
        workspace, conn, problem=problem, group_id=group_id,
        pipeline_id=pipeline_id, body=body, rounds=turn,
        verdict=verdict, status=status,
        resumed_from=(resumed.source_pipeline_id if resumed else ""))
    _landing.record(
        conn, problem=problem, group_id=group_id,
        pipeline_id=pipeline_id, decision_id=decision_id,
        objective=objective, situation=situation, path=path,
        status=status, rounds=turn, verdict_json=verdict_json)
    if not accepted:
        fired = fired_criteria(verdict)
        summary = "\n".join(f"- {c}"
                            for c in (verdict or {}).get("criticisms", []))
        # The path FIRST: `outcomes._theorize_result_lines` truncates
        # this detail at 1200 chars on the batch scoreboard, and the one
        # line the wake cannot do without is the one that lets it read
        # the document.
        lines = [f"the document landed anyway, as the record of what was "
                 f"tried: `{path}`"]
        if rigour_is_defective(verdict):
            # Citability follows criterion 2, not the status: this
            # document's theorems were never re-derived, so a later wake
            # citing them would be citing an attempt as a result.
            lines.append(RIGOUR_DEFECTIVE
                         + " — its results are attempts, not established")
        lines.append(
            f"{turn} round(s), the reviewer's last ruling still fired"
            + (f" on criterion {', '.join(fired)}" if fired else "")
            + f":\n{summary}")
        print(f"[theorist] {problem} g{group_id}: rejected after {turn} "
              f"round(s) — landed as the record at {path}", flush=True)
        return _fail("theory_rejected", "\n".join(lines),
                     headline=REJECTED_DETAIL)

    _settle(conn, decision_id, outcome="success", detail=path)
    print(f"[theorist] {problem} g{group_id}: accepted after {turn} "
          f"round(s) — {path}", flush=True)
    return PipelineResult(outcome="success")


__all__ = ["run_theorist", "REJECTED_DETAIL", "SPAWN_DIED_DETAIL",
           "NO_REQUEST_DETAIL", "DEFAULT_ROUNDS", "parse_theory_verdict"]
