"""Outer entry — full agent integration: `run_strategist` (the
trigger_context / agent / self_verify / commit stage pipeline, the
Adversary revision loop and its mechanical delta gate), plus the
proposal-package gate (`package_gate_applies`, `verify_proposal_package`,
`_format_rebuttal`, `PROPOSAL_BASENAME`) that gate feeds. Also the
routine-wake KB curation sidecar (`_apply_kb_curation`), the
discard/persist bookkeeping (`_discard_proposal`, `_persist_plan`), and
the rc-to-reason aliases (`_rc_to_reason`, `_adversary_rc_reason`).

Split out of `strategist.py` 2026-08-28 (Phase B, B1) unchanged.
`PROPOSAL_BASENAME` moved here rather than with the decision-kind
vocabulary in `model.py`: both its consumers (`verify_proposal_package`,
`_discard_proposal`) live in this module.
"""
from __future__ import annotations

import json
import sqlite3
import time as _time
import uuid
from pathlib import Path
from typing import Any

from ...state import db, failures as _failures

from .commit import commit_decisions
from .model import Decision, _PACKAGE_EXEMPT_KINDS, parse_decisions
from .verify import _group_retired_status, verify_decisions


PROPOSAL_BASENAME = "proposal.md"


def package_gate_applies(decisions, trigger_kind: str | None) -> bool:
    return any(d.kind not in _PACKAGE_EXEMPT_KINDS for d in decisions)


def verify_proposal_package(decisions, attempts_dir) -> tuple[
        "str | None", "dict[str, str] | None", "str | None"]:
    """Package-side checks for a gated batch: proposal file present,
    four-section contract, and the ≥1-experiment rule (endgame batches
    exempt). Returns (body, sections, err)."""
    from ...state import programme
    path = attempts_dir / PROPOSAL_BASENAME
    if not path.exists():
        return None, None, (
            "this batch moves the route, so it must carry a Programme "
            f"proposal: Write `{PROPOSAL_BASENAME}` (bare filename, in "
            "your attempts dir) with the four sections `# <Title>`, "
            "`## Argument`, `## Proof`, `## Roadmap`. Then re-emit "
            "decision.json (unchanged if it was already right).")
    try:
        body = path.read_text(encoding="utf-8")
    except OSError as e:
        return None, None, f"{PROPOSAL_BASENAME} unreadable: {e}"
    sections, err = programme.parse_proposal(body)
    if err:
        return None, None, err
    # The ≥1-experiment quota lived here until 2026-08-16 (owner
    # ruling). A per-batch quota gets satisfied with manufactured
    # experiments — the same pathology as the stalled-root Inject tax —
    # while the actual invariant ("a batch must not leave the group in
    # dead air") is already enforced mechanically by the stalled-delta
    # gate and the parked-root gate in `verify_decisions`, both of which
    # fire on STATE, not on decision-kind counts.
    # The `Roadmap:` presence check is GONE (2026-08-11). Its history is
    # the argument: it began as a substring match of the cited phrase
    # against the free-prose Roadmap — a gate detecting free text, which
    # the design rules forbid — and it bounced whole batches five times
    # over phrasing (2026-08-03 feedback #4, operator ruling: the Roadmap
    # stays pure NL). What survived that narrowing checked only that SOME
    # line began `Roadmap:`, which `Roadmap: x` satisfies. It could not
    # fail a batch that was actually wrong and it could fail one that was
    # right, while remaining the last mechanical reader of a field the
    # Strategist writes as prose. Whether an experiment tests the entry
    # it claims is the Adversary's, under criteria 1/4, and always was.
    return body, sections, None


def _format_rebuttal(verdict: dict, round_no: int,
                     rounds_left: int,
                     length_warn: "str | None" = None) -> str:
    crits = "\n".join(f"- {c}" for c in verdict.get("criticisms", []))
    # 07-29 bloat ruling: revisions must not answer objections by
    # accretion (observed: each rebut round ADDED argumentation;
    # proposal 31.6k on a toy batch). The base sentence rides every
    # rebuttal; the over-budget escalation appears only when a length
    # warning actually tripped — a rare line keeps its force.
    over = (f"\n{length_warn}\nThe revision must come back smaller.\n"
            if length_warn else "")
    return (
        f"ADVERSARY REBUTTAL (round {round_no}; {rounds_left} revision "
        "round(s) left before this proposal is discarded and the next "
        "wake restarts fresh):\n" + crits + "\n" + over +
        "For EACH point: either revise (rewrite proposal.md — and "
        "decision.json if the experiments change) or defend (keep your "
        "position and answer the point inside `## Argument`). Revise by "
        "cutting and correcting in place, not by appending defenses. "
        "Do not concede points you believe are misreadings. Re-emit "
        "decision.json in every case.")


# ---------------------------------------------------------------------
# Outer entry — full agent integration
# ---------------------------------------------------------------------


def run_strategist(conn: sqlite3.Connection, *, problem: str,
                   trigger_kind: str, tick: int,
                   workspace: Path,
                   intent: "Any",
                   pipeline_id: str,
                   pending_review_id: int | None = None,
                   group_id: "int | None" = None) -> "Any":
    """Full Strategist pipeline (Phase 2 §2.4).

    Stages:
      1. trigger_context   — compile Strategist-flavoured Context.md
      2. agent             — spawn LLM, drops `decision.json` in
                             attempts_dir
      3. self_verify       — parse_decisions + verify_decisions
      4. commit            — commit_decisions side effects
      5. status mapping    — Noop-only batch / schema invalid →
                             infra-reason (no attempts++); commit
                             → success

    Returns `PipelineResult` with one of:
      - outcome='success' on a clean commit (one or more decisions,
        at least one non-Noop)
      - outcome='failed', failure_reason='strategist_noop' when the
        batch contains only Noop decisions (infra so cascade_one
        doesn't burn root.attempts)
      - outcome='failed', failure_reason='strategist_schema_invalid'
        when parse/verify rejects the agent's output (all-or-nothing
        at this stage — no row is committed if any decision fails)
      - outcome='failed', failure_reason='agent_no_output' if no
        decision.json produced
      - provider rc-based reasons (quota / spawn_fast_fail / ...) on
        agent.spawn_llm rc != 0
    """
    from ... import agent
    from ...core import config
    from .. import PipelineResult, PROMPT_DIR
    from ...agent.phase2_context import compile_strategist_context

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    problem_dir = db.problem_dir(workspace, problem)
    # Per-trigger prompt: each trigger has its own focused prompt so
    # the agent sees only the guidance relevant to this wake's kind
    # (routine / pending_review / inject_batch_done).
    # Loader validates that every TRIGGER_KIND has a corresponding
    # file at startup via test_strategist_prompts_cover_all_triggers.
    # A stall wake reads the batch-done prompt: it carries the
    # mandatory-advance rule the rescue exists to invoke (there is no
    # stall.md — the identity split is for the DB record, not for a
    # different conversation).
    _prompt_kind = ("inject_batch_done" if trigger_kind == "stall"
                    else trigger_kind)
    prompt_path = PROMPT_DIR / "strategist" / f"{_prompt_kind}.md"
    if not prompt_path.exists():
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_schema_invalid",
            failure_detail=(
                f"missing prompt file for trigger_kind={trigger_kind!r}: "
                f"{prompt_path}"
            ),
        )

    # Stage 1 — Context.md
    compile_strategist_context(
        conn, problem=problem, trigger_kind=trigger_kind,
        attempts_dir=attempts_dir, workspace=workspace, intent=intent,
        pending_review_id=pending_review_id, group_id=group_id,
    )

    # Stage 2 — agent spawn. Mint a session id so the in-pipeline
    # revision rounds can resume the same claude session and see the
    # framework's verify error / Adversary rebuttal inline.
    # Thinking is legal work (research_mode_design.md §0): the
    # strategist cap is a hang guard, not a work budget.
    strategist_timeout = config.get(
        "strategist.timeout_sec", default=10800,
        env_var="ASTERISM_STRATEGIST_TIMEOUT_SEC", cast=int,
    )
    sid = str(uuid.uuid4())
    # D8 (2026-07-24): a fresh problem has no prior batches — the
    # meta-analysis / reopen-promise paragraphs render only once
    # history exists (conditional blocks, wording untouched).
    has_history = conn.execute(
        "SELECT 1 FROM strategist_decisions WHERE problem = ? LIMIT 1",
        (problem,)).fetchone() is not None
    # has_kb gates the routine wake's lesson-KB curation block — an
    # empty KB renders neither the Context surface nor the instruction.
    from ...state import kb as _kb
    has_kb = bool(_kb.global_lessons(conn, problem))
    # The framework's tools reach this wake over MCP, not a shell (see
    # knowledge/mcp_tools.py). No gateway session: the Strategist has no
    # Lean file open, and registering one would hold a backend slot for
    # nothing.
    from .. import write_tools_mcp_config as _write_tools_cfg
    tools_cfg = _write_tools_cfg(attempts_dir, workspace, seat="strategist")
    rc = agent.spawn_llm(
        kind="strategist", prompt_path=prompt_path,
        problem_dir=problem_dir, attempts_dir=attempts_dir,
        session_id=sid, timeout_sec=strategist_timeout,
        mcp_config_path=tools_cfg,
        prompt_flags={"has_history": has_history, "has_kb": has_kb},
    )
    # Persist the plan note BEFORE any outcome branching: the note is the
    # agent's memory of its own thinking — worth keeping even when the
    # spawn then fails parse/verify (and on rc!=0, if it got that far).
    _persist_plan(problem_dir, attempts_dir, group_id)
    if rc != 0:
        return PipelineResult(
            outcome="failed",
            failure_reason=_rc_to_reason(rc),
            failure_detail=f"agent rc={rc}",
        )

    # Stage 3-4 — parse + verify + the proposal-package gate + the
    # Adversary, unified into one N-round revision loop on the same
    # strategist session (research_mode_design.md §3). Mechanical
    # verify errors and Adversary rebuttals SHARE the round counter
    # (v14 ruling). Parse failures get the same single corrective turn
    # as a missing file (2026-08-25 reversal of "malformed means
    # session-level breakage": p324's session was healthy — 10 minutes
    # of research on disk, one malformed decision.json — and died for
    # want of one "rewrite it" turn).
    max_rounds = config.get(
        "strategist.verify_retry", default=6,
        env_var="ASTERISM_STRATEGIST_VERIFY_RETRY", cast=int,
    )
    decision_path = attempts_dir / "decision.json"

    # Quota-park budget for this wake (2026-08-08). A debate that
    # collides with the subscription reset must sleep to it rather than
    # burn the accumulated rounds — but only so far: the queue row's
    # lease is reclaimed on AGE alone at LEASE_TTL_SEC even with this
    # thread alive, and a reclaimed row means a second Strategist on
    # this same group. Budget = what is left of 80% of the TTL after
    # everything this wake has already spent.
    _wake_t0 = _time.monotonic()

    def _park_budget() -> float:
        from ...core.dispatcher import LEASE_TTL_SEC
        return (LEASE_TTL_SEC * 0.8) - (_time.monotonic() - _wake_t0)

    def _quota_park(label: str) -> bool:
        from ...core import quota_wait as _qw
        return _qw.park_in_pipeline(f"{problem} {label}",
                                    budget_sec=_park_budget())

    def _read_and_parse() -> tuple[
        list[Decision] | None, str, str
    ]:
        """Returns (decisions, parse_err, missing_reason). When the
        file is missing, missing_reason is non-empty for
        agent_no_output mapping."""
        if not decision_path.exists():
            return None, "", "decision.json not produced"
        try:
            text = decision_path.read_text(encoding="utf-8")
        except OSError as e:
            return None, "", f"decision.json unreadable: {e}"
        ds, perr = parse_decisions(text)
        return ds, perr, ""

    decisions, parse_err, missing = _read_and_parse()
    if missing or decisions is None:
        # One corrective turn before the wake dies at the file stage.
        # Three shapes end a session with the WORK all there but no
        # usable decision.json: the model narrates its decision in
        # prose instead of calling write_file, OpenCode occasionally
        # ends a healthy stream early with a near-empty final that the
        # tool loop accepts as the answer (5/46 wakes on the flagship's
        # first generations, 2026-08-25 — each death threw away 20+
        # minutes of research), and the file lands malformed past what
        # the lenient parse absorbs (p324, same day). Resuming the SAME
        # session costs one cheap turn and keeps everything it learned;
        # a second miss still dies below.
        _defect = missing or f"decision.json does not parse ({parse_err})"
        print(f"[strategist] {problem}: {_defect} — one corrective "
              f"resume turn", flush=True)
        rc_fix = agent.spawn_llm(
            kind="strategist", prompt_path=prompt_path,
            problem_dir=problem_dir, attempts_dir=attempts_dir,
            session_id=sid, is_retry=True,
            retry_context=(
                ("Your turn ended but decision.json was NOT written — "
                 "the research is only real once it lands on disk. "
                 "Write decision.json NOW with write_file (and "
                 "proposal.md if your batch carries one). If your last "
                 "message was cut off, reconstruct the decision from "
                 "your notes above.")
                if missing else
                (f"Your decision.json is not valid JSON — {parse_err}. "
                 "Rewrite the ENTIRE file NOW with write_file as one "
                 "valid JSON array of decision objects; keep the same "
                 "decisions, fix only the syntax.")),
            timeout_sec=strategist_timeout,
            mcp_config_path=tools_cfg,
        )
        _persist_plan(problem_dir, attempts_dir, group_id)
        if rc_fix == 0:
            decisions, parse_err, missing = _read_and_parse()
    if missing:
        return PipelineResult(
            outcome="failed", failure_reason="agent_no_output",
            failure_detail=missing + " (after one corrective turn)",
        )
    if decisions is None:
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_schema_invalid",
            failure_detail=f"parse: {parse_err} (after one corrective turn)",
        )

    from ...state import programme as _programme
    from .. import adversary as _adversary

    dialogue: list[dict] = []
    rounds_used = 0
    package_verdict: "dict | None" = None
    proposal_body: "str | None" = None
    first_err: "str | None" = None
    #: mechanical delta gate (owner design 2026-08-28): the body the
    #: Adversary last rejected, the rebuttal it issued, and how many
    #: consecutive revision turns came back byte-identical.
    _last_judged: "str | None" = None
    _last_rebuttal: "str | None" = None
    _no_delta = 0
    while True:
        # Round-boundary race-guard: the authoring group can be retired
        # mid-dialogue (ancestor ReturnToParent cascade). Ask before
        # spending a verify + adversary round — the batch of a retired
        # charter has nowhere legal to land, so the wake self-aborts
        # instead of debating on (fold day 2026-08-19: 11 rounds burned
        # past the flip). The commit door below backstops the window
        # between this check and Stage 5.
        _retired = _group_retired_status(conn, problem, group_id)
        if _retired is not None:
            _discard_proposal(
                conn, problem, proposal_body, dialogue, rounds_used,
                f"authoring group retired ({_retired}) mid-wake",
                attempts_dir, group_id=group_id, channel="group_retired")
            return PipelineResult(
                outcome="failed", failure_reason="group_retired",
                failure_detail=(
                    f"group {group_id} is {_retired}; a retired charter "
                    "accepts no new batch"))
        err = verify_decisions(decisions, conn, problem=problem,
                               workspace=workspace,
                               trigger_kind=trigger_kind,
                               group_id=group_id)
        err_is_rebuttal = False
        if not err and package_gate_applies(decisions, trigger_kind):
            proposal_body, sections, err = verify_proposal_package(
                decisions, attempts_dir)
            # ── mechanical delta gate (owner design 2026-08-28): a
            # byte-identical resubmission never reaches the judge — it
            # is an ACCIDENT signature, not author conviction (every
            # byte-identical debate on record traces to the zen
            # resume-amnesia era: the revision turn succeeded but never
            # touched the file, and the judge re-fired the same
            # rebuttal at the same bytes until the round cap). Bounce
            # with a mechanical notice; three consecutive no-deltas
            # discard — a fresh wake re-passes cheaply (73-77% within
            # two revisions, measured 2026-08-28).
            if (not err and _last_judged is not None
                    and proposal_body == _last_judged):
                _no_delta += 1
                if _no_delta >= 3:
                    _discard_proposal(
                        conn, problem, proposal_body, dialogue,
                        rounds_used,
                        "proposal byte-identical for 3 consecutive "
                        "revision rounds", attempts_dir,
                        group_id=group_id, channel="strategist_no_delta")
                    return PipelineResult(
                        outcome="failed",
                        failure_reason="strategist_no_delta",
                        failure_detail=(
                            "three consecutive revision rounds left "
                            "proposal.md byte-identical; pending "
                            "rebuttal recorded in programme_revisions"))
                print(f"[strategist] {problem}: delta gate — proposal "
                      f"byte-identical, judge skipped (no-delta "
                      f"{_no_delta}/3)", flush=True)
                err = (
                    "mechanical delta gate: proposal.md is "
                    "byte-identical to the version the Adversary just "
                    f"rejected (no-delta {_no_delta}/3; at 3 this "
                    "proposal is discarded and the next wake restarts "
                    "fresh). The revision never reached the file — "
                    "edit proposal.md to address the pending rebuttal, "
                    "or change the batch.\n\n"
                    "Pending rebuttal (unchanged):\n"
                    + (_last_rebuttal
                       or "(see the previous turn's rebuttal)"))
                err_is_rebuttal = True
            elif not err:
                _no_delta = 0
            if not err:
                proof_warn = _programme.length_warning(
                    sections, proposal_body)
                if proof_warn:
                    print(f"[strategist] {problem}: {proof_warn}",
                          flush=True)
                verdict, aerr, arc = _adversary.review(
                    round_no=rounds_used + 1,
                    attempts_dir=attempts_dir, problem_dir=problem_dir,
                    conn=conn, problem=problem,
                    proposal_body=proposal_body, decisions=decisions,
                    dialogue=dialogue, proof_warn=proof_warn,
                    group_id=group_id, quota_park=_quota_park)
                if arc != 0:
                    _discard_proposal(
                        conn, problem, proposal_body, dialogue,
                        rounds_used,
                        f"adversary spawn rc={arc}", attempts_dir,
                        group_id=group_id,
                        channel=_adversary_rc_reason(arc))
                    return PipelineResult(
                        outcome="failed",
                        failure_reason=_adversary_rc_reason(arc),
                        failure_detail=f"adversary rc={arc}")
                if verdict is None:
                    _discard_proposal(
                        conn, problem, proposal_body, dialogue,
                        rounds_used,
                        "adversary produced no ruling", attempts_dir,
                        group_id=group_id, channel="agent_no_output")
                    return PipelineResult(
                        outcome="failed",
                        failure_reason="agent_no_output",
                        failure_detail=f"adversary: {aerr}")
                if verdict["verdict"] == "pass":
                    package_verdict = verdict
                    break
                # Rebuttal: the criticisms target THIS body — keep it
                # with them so the next (fresh) judge reads the round
                # as documents (fresh-per-round, design §3).
                dialogue.append({"round": rounds_used + 1,
                                 "role": "adversary",
                                 "criticisms": verdict["criticisms"],
                                 "proposal": proposal_body})
                # rounds_left = revisions still available AFTER this
                # rebuttal: a retry fires whenever rounds_used <
                # max_rounds, so exactly max_rounds - rounds_used
                # remain (off-by-one here once taught "0 left" while
                # the loop granted one more).
                err = _format_rebuttal(
                    verdict, rounds_used + 1,
                    max_rounds - rounds_used,
                    length_warn=proof_warn)
                err_is_rebuttal = True
                # delta-gate bookkeeping: THIS body is what the judge
                # rejected; the next revision must change it.
                _last_judged = proposal_body
                _last_rebuttal = err
        if not err:
            break  # verify clean; exempt batches skip the package gate
        if first_err is None:
            first_err = err
        if rounds_used >= max_rounds:
            if err_is_rebuttal and proposal_body is not None:
                # Exhaustion on the adversarial channel discards the
                # proposal AND the session: the rejected draft + full
                # criticism go to the DB for audit; the next wake gets
                # one line and re-derives blind (design §1/§3).
                _discard_proposal(
                    conn, problem, proposal_body, dialogue, rounds_used,
                    "adversary rebuttal", attempts_dir,
                    group_id=group_id,
                    channel="strategist_proposal_rejected")
                return PipelineResult(
                    outcome="failed",
                    failure_reason="strategist_proposal_rejected",
                    failure_detail=(
                        f"adversary rejected after {rounds_used} "
                        "revision round(s); proposal + criticisms "
                        "recorded in programme_revisions"))
            _discard_proposal(
                conn, problem, proposal_body, dialogue, rounds_used,
                "package verify rejected", attempts_dir,
                group_id=group_id,
                channel="strategist_schema_invalid")
            return PipelineResult(
                outcome="failed",
                failure_reason="strategist_schema_invalid",
                failure_detail=(f"verify (round {rounds_used}): {err}; "
                                f"first-attempt: {first_err}"),
            )
        rounds_used += 1
        # Same class as the judge's infra retry (task #132): this wake
        # already holds a parsed batch (and possibly rounds of
        # criticism); a provider-side rc on the revision spawn must cost
        # a re-spawn, not the accumulated work. Session id is reused —
        # `--resume` on the same sid is what carries the revision.
        _infra_tries = 0
        while True:
            rc2 = agent.spawn_llm(
                kind="strategist", prompt_path=prompt_path,
                problem_dir=problem_dir, attempts_dir=attempts_dir,
                session_id=sid, is_retry=True, retry_context=err,
                timeout_sec=strategist_timeout,
                mcp_config_path=tools_cfg,
            )
            if rc2 != 0 and _failures.is_infra(_rc_to_reason(rc2)):
                # Ask the ledger BEFORE spending the retry budget: an
                # expired subscription window announces its own end
                # time, and 2×15s against it is what cost an 8-round
                # debate (2026-08-07). Parking resumes the SAME sid, so
                # the author keeps its position in the argument.
                if _quota_park(f"revision round {rounds_used}"):
                    continue
            if (rc2 != 0
                    and _failures.is_infra(_rc_to_reason(rc2))
                    and _infra_tries < _adversary.INFRA_SPAWN_RETRIES):
                _infra_tries += 1
                print(f"[strategist] {problem}: revision round "
                      f"{rounds_used} spawn rc={rc2} (infra) — retry "
                      f"{_infra_tries}/{_adversary.INFRA_SPAWN_RETRIES} "
                      f"in {_adversary.INFRA_RETRY_BACKOFF_SEC:.0f}s",
                      flush=True)
                _time.sleep(_adversary.INFRA_RETRY_BACKOFF_SEC)
                continue
            break
        _persist_plan(problem_dir, attempts_dir, group_id)  # retry may rewrite it
        if rc2 != 0:
            _discard_proposal(
                conn, problem, proposal_body, dialogue, rounds_used,
                f"revision spawn rc={rc2}", attempts_dir,
                group_id=group_id, channel=_rc_to_reason(rc2))
            return PipelineResult(
                outcome="failed",
                failure_reason=_rc_to_reason(rc2),
                failure_detail=(
                    f"revision round {rounds_used} rc={rc2}; "
                    f"pending: {err}"
                ),
            )
        decisions, parse_err, missing = _read_and_parse()
        if missing or decisions is None:
            detail = missing or f"parse: {parse_err}"
            _discard_proposal(
                conn, problem, proposal_body, dialogue, rounds_used,
                "revision round produced no decision.json",
                attempts_dir, group_id=group_id,
                channel="strategist_schema_invalid")
            return PipelineResult(
                outcome="failed",
                failure_reason="strategist_schema_invalid",
                failure_detail=(
                    f"revision round {rounds_used} output: {detail}; "
                    f"pending: {err}"
                ),
            )

    # Stage 5 — commit + outcome mapping
    # Commit door: last look before side effects. The round loop above
    # checks at every boundary, but the group can flip terminal between
    # the final pass verdict and here; `commit_decisions` itself raises
    # on this as the any-caller backstop, and a raise there would be
    # mis-filed as a framework bug — so the known race exits cleanly.
    _retired = _group_retired_status(conn, problem, group_id)
    if _retired is not None:
        _discard_proposal(
            conn, problem, proposal_body, dialogue, rounds_used,
            f"authoring group retired ({_retired}) before commit",
            attempts_dir, group_id=group_id, channel="group_retired")
        return PipelineResult(
            outcome="failed", failure_reason="group_retired",
            failure_detail=(
                f"group {group_id} is {_retired}; a retired charter "
                "accepts no new batch"))
    if all(d.kind == "Noop" for d in decisions):
        # Pure-Noop batch (one or more Noops): commit audit rows so
        # last_strategist_at + bootstrap_done advance, but map the
        # pipeline outcome to the infra-reason so cascade_one doesn't
        # try to attempts++ on the root. A mixed batch with at least
        # one non-Noop decision falls through to the success path
        # below — there's real work in it.
        try:
            commit_decisions(
                decisions, conn, problem=problem, tick=tick,
                trigger_kind=trigger_kind, workspace=workspace,
                group_id=group_id,
            )
        except Exception as e:
            return PipelineResult(
                outcome="failed",
                failure_reason="strategist_schema_invalid",
                failure_detail=f"commit raised: {type(e).__name__}: {e}",
            )
        if trigger_kind == "routine":
            _apply_kb_curation(conn, problem=problem,
                               attempts_dir=attempts_dir)
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_noop",
            failure_detail=" | ".join(
                str(d.reason or "") for d in decisions
            ),
        )

    try:
        outcomes = commit_decisions(
            decisions, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, workspace=workspace,
            group_id=group_id,
        )
    except Exception as e:
        # Commit must succeed once verify passed; any error here is
        # a framework bug. Surface as schema_invalid so dispatcher
        # doesn't burn root.attempts on a framework-side issue.
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_schema_invalid",
            failure_detail=f"commit raised: {type(e).__name__}: {e}",
        )

    if package_verdict is not None and proposal_body is not None:
        # Passed proposal → the Programme revision chain advances in
        # the same wake as its batch (rev↔batch link via batch_id).
        # PROGRAMME.md render is best-effort — the DB row is the SoT.
        batch_id = next(
            (o.batch_id for o in outcomes if o.batch_id), None)
        _programme.record_pass(
            conn, problem, proposal_body, package_verdict, dialogue,
            rounds_used, batch_id, group_id=group_id)
        conn.commit()
        try:
            _programme.render(conn, problem, problem_dir,
                              group_id=group_id)
        except OSError as e:
            print(f"[strategist] PROGRAMME.md render failed: {e}",
                  flush=True)

    if trigger_kind == "routine":
        # Curation applies only after the wake's decisions committed —
        # a rejected batch (retry loop above) must not half-apply a
        # sidecar the agent may still rewrite.
        _apply_kb_curation(conn, problem=problem,
                           attempts_dir=attempts_dir)

    kinds = ",".join(d.kind for d in decisions)
    row_ids = ",".join(str(o.decision_row_id) for o in outcomes)
    # Framework feedback (dedicated tail step) — fired here, after every
    # `--resume <sid>` (main + optional verify-retry) is done, so the feedback
    # turn never pollutes a verify-retry's session. No-op unless feedback is on.
    from .. import _feedback
    _feedback.attempt_feedback(
        kind="strategist", seat="strategist", sid=sid,
        slug=str(trigger_kind or "strategist"),
        outcome="success", problem_dir=problem_dir,
        attempts_dir=attempts_dir, workspace=workspace)
    return PipelineResult(
        outcome="success",
        failure_reason="",
        failure_detail=(
            f"committed {len(decisions)} decision(s): [{kinds}] "
            f"(decision_rows=[{row_ids}])"
        ),
    )


_KB_CURATION_MAX_OPS = 10


def _apply_kb_curation(conn: "Any", *, problem: str,
                       attempts_dir: Path) -> None:
    """Routine-wake KB curation (2026-07-13, user call; moved from the
    retired audit wake 2026-07-25): apply the optional
    `kb_curation.json` sidecar the agent may drop next to
    decision.json. Ops:

      {"op": "delete", "id": N, "reason": "..."}
      {"op": "merge", "keep_id": N, "absorb_ids": [..],
       "title": "...", "body": "...", "reason": "..."}

    Deliberately a sidecar, NOT a decision kind: curation is
    belief-store maintenance (same class as the direct `_plan.md`
    curation), never problem-state advance — keeping it out of
    decision.json means it can never satisfy the stall-advance delta
    gate, and no DB CHECK migration is needed. Only the routine runner
    calls this, so the power is structurally routine-only.

    Strict all-or-nothing: any invalid op rejects the whole file with
    a loud `[kb-curation]` line and nothing is applied — but the wake
    itself never fails on it (the sidecar is best-effort; the wake's
    deliverables are its decisions + note). Applied ops print full
    pre-image snapshots to the daemon log as the audit trail."""
    from ...state import kb

    path = attempts_dir / "kb_curation.json"
    if not path.exists():
        return

    def _reject(msg: str) -> None:
        print(f"[kb-curation] {problem}: rejected, nothing applied — "
              f"{msg}", flush=True)

    try:
        ops = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return _reject(f"unreadable/invalid JSON: {e}")
    if not isinstance(ops, list) or not ops:
        return _reject("must be a non-empty JSON array of ops")
    if len(ops) > _KB_CURATION_MAX_OPS:
        return _reject(f"{len(ops)} ops exceeds the per-wake cap of "
                       f"{_KB_CURATION_MAX_OPS}")

    eligible = {int(r["id"]) for r in kb.global_lessons(conn, problem)}
    seen_ids: set[int] = set()

    def _claim(raw: "Any", i: int, field: str) -> int | None:
        if not isinstance(raw, int) or isinstance(raw, bool):
            _reject(f"op #{i}: {field} must be an integer id")
            return None
        if raw not in eligible:
            _reject(f"op #{i}: id {raw} is not one of this problem's "
                    "global lessons")
            return None
        if raw in seen_ids:
            _reject(f"op #{i}: id {raw} referenced by more than one op")
            return None
        seen_ids.add(raw)
        return raw

    parsed: list[dict] = []
    for i, op in enumerate(ops):
        if not isinstance(op, dict):
            return _reject(f"op #{i}: not a JSON object")
        if not str(op.get("reason", "")).strip():
            return _reject(f"op #{i}: non-empty source-checked 'reason' "
                           "is required")
        kind = op.get("op")
        if kind == "delete":
            if _claim(op.get("id"), i, "id") is None:
                return None
        elif kind == "merge":
            if _claim(op.get("keep_id"), i, "keep_id") is None:
                return None
            absorb = op.get("absorb_ids")
            if not isinstance(absorb, list) or not absorb:
                return _reject(f"op #{i}: absorb_ids must be a non-empty "
                               "list")
            for a in absorb:
                if _claim(a, i, "absorb_ids entry") is None:
                    return None
            if not str(op.get("title", "")).strip():
                return _reject(f"op #{i}: merged 'title' must be "
                               "non-empty")
        else:
            return _reject(f"op #{i}: unknown op {kind!r} (delete|merge)")
        parsed.append(op)

    for op in parsed:
        if op["op"] == "delete":
            snap = kb.delete_global_lesson(
                conn, entry_id=op["id"], problem=problem)
            print(f"[kb-curation] {problem}: deleted lesson "
                  f"[id-{op['id']}] reason={op['reason']!r} "
                  f"snapshot={dict(snap) if snap else None}", flush=True)
        else:
            snaps = kb.merge_global_lessons(
                conn, keep_id=op["keep_id"],
                absorb_ids=[int(a) for a in op["absorb_ids"]],
                problem=problem, title=str(op["title"]),
                body=str(op.get("body", "")))
            print(f"[kb-curation] {problem}: merged "
                  f"{op['absorb_ids']} into [id-{op['keep_id']}] "
                  f"reason={op['reason']!r} "
                  f"pre-images={[dict(r) for r in snaps or []]}",
                  flush=True)


def _discard_proposal(conn, problem: str,
                      proposal_body: "str | None",
                      dialogue: list, rounds_used: int,
                      reason: str,
                      attempts_dir: "Path | None" = None,
                      group_id: "int | None" = None,
                      channel: "str | None" = None) -> None:
    """Record a proposal that did NOT commit, whichever channel dropped
    it (Adversary refutation / package verify / revision spawn failure /
    unusable revision output).

    Pre-v34 only the Adversary path left a row, so a batch dropped by
    the mechanical channels vanished without trace while its plan note
    — persisted before the batch is judged — survived asserting the
    dispatch. The next wake then had to reconstruct that from three
    artifacts (07-29 SG ×2). No proposal at all (exempt batch: Noop /
    RequestUserAmend / FetchPaper) → nothing to record; the plan note's
    provenance stamp still covers those.

    `attempts_dir` is the fallback source: an early verify rejection
    fires BEFORE the package gate reads `proposal.md`, so the body the
    agent wrote exists only on disk at that point."""
    if not proposal_body and attempts_dir is not None:
        try:
            proposal_body = (attempts_dir / PROPOSAL_BASENAME).read_text(
                encoding="utf-8")
        except OSError:
            proposal_body = None
    if not proposal_body:
        return
    from ...state import programme as _programme
    try:
        _programme.record_rejection(conn, problem, proposal_body,
                                    dialogue, rounds_used,
                                    discard_reason=reason,
                                    group_id=group_id,
                                    discard_channel=channel)
        conn.commit()
    except Exception as e:  # noqa: BLE001 — audit record, never fatal
        print(f"[strategist] {problem}: discard record failed: "
              f"{type(e).__name__}: {e}", flush=True)


def _persist_plan(problem_dir: Path, attempts_dir: Path,
                  group_id: "int | None" = None) -> None:
    """Persist the Strategist's `_plan.md` (private cross-wake note, see
    `_drafts.persist_plan_note`) + one telemetry line. Best-effort."""
    from .. import _drafts
    n = _drafts.persist_plan_note(problem_dir=problem_dir,
                                  attempts_dir=attempts_dir,
                                  group_id=group_id)
    if n is not None:
        over = (" (over soft cap)"
                if n > _drafts.PLAN_NOTE_SOFT_CAP else "")
        print(f"[strategist] plan note updated: {n} chars{over}",
              flush=True)


def _rc_to_reason(rc: int, kind: str = "strategist") -> str:
    """Channel failure_reason for an agent rc — thin alias of the registry's
    `failures.rc_to_reason` (task #5: the last per-pipeline mirror of the rc
    taxonomy; kept as a module-local name for the two call sites + tests).

    `kind` names the seat, which is how the provider's `rc_contract`
    declaration is found. The Strategist and the Adversary sit on
    different providers routinely (2026-08 runs: NL on opus-5, judge
    moved between seats mid-run), so an rc from the judge must be read
    against the JUDGE's contract, not the author's."""
    from ...llm import capabilities as _caps
    from ...state.failures import rc_to_reason
    return rc_to_reason(rc, rc_contract=_caps.for_kind(kind).rc_contract)


def _adversary_rc_reason(rc: int) -> str:
    """The judge's rc, read against the JUDGE's seat. A named function
    rather than an inline second argument: a bare string literal beside
    `failure_reason=` is what the registry's AST drift scan reads as a
    new failure reason."""
    return _rc_to_reason(rc, "adversary")
    if rc == 126:
        return "quota_exhausted"
    if rc == 127:
        return "missing_dep"
    if rc == 128:
        return "spawn_fast_fail"  # stuck thinking — treat as infra
    return "spawn_fast_fail"
