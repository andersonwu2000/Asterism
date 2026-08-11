"""Formalizer intake stage (update_plan_2026_07 #1).

First turn on a fresh session: the agent reads Context.md (Programme
`## Proof` + assignment + tree state) and writes an `intake.json`
sentinel — `{"verdict":"proceed"}` or
`{"verdict":"decline","reason":<reason>,"note":...}` with reason one of
  * `return_to_nl` — the argument does not settle this assignment;
  * `unprovable` — a concrete instance breaks the statement (task #124,
    archaeology-backed: all 27 historical disproved goals were killed by
    a FRESH agent's unprovable decline within 1-3 attempts, never by the
    parent that transcribed them — the falsity scan belongs at the
    fresh, zero-sunk-cost turn. Note must carry the counterexample;
    an empty note fails open to proceed. Maps through the same
    DECLINE_TO_FAILURE_REASON as the work-turn directive, so the
    cascade semantics (`agent_infeasible` → disproved) are identical.)

Behavior contract (user ruling 2026-07-27 — intake is an ECONOMY gate,
not a soundness gate; the work-turn `-- decline:` channel remains
authoritative):
  * decline verdict     → caller exits before presearch / work spawn.
  * proceed             → caller continues the SAME session
                          (spawn_llm continuation=True via the retry
                          helper's `initial_sid`).
  * missing / malformed sentinel, timeout, other spawn error
                        → proceed WITHOUT a session (caller falls back
                          to the classic single-turn cold flow) — a
                          broken intake never blocks good work.
  * quota / missing-dep / shutdown rc → surfaced to the caller so the
    dispatcher's infra handling (cooldown / teardown) applies as usual.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from .. import agent
from ..llm.base import SpawnRC


#: rcs the caller must convert into its pipeline's usual infra result
#: instead of degrading to a cold work spawn (quota burn / teardown).
INTAKE_INFRA_RCS = (SpawnRC.QUOTA_EXHAUSTED, SpawnRC.MISSING_DEP,
                    SpawnRC.SHUTDOWN)

_SENTINEL = "intake.json"
_VALID_DECLINE_REASONS = ("return_to_nl", "unprovable")


@dataclass
class IntakeOutcome:
    #: session to continue via the retry helper's initial_sid; None =
    #: intake spawn unusable → classic cold flow.
    sid: "str | None" = None
    #: (reason, note) when the agent declined at intake.
    declined: "tuple[str, str] | None" = None
    #: one of INTAKE_INFRA_RCS when the spawn died on infra — caller
    #: returns its pipeline's matching infra result.
    infra_rc: "int | None" = None


def intake_timeout_sec(workspace: "Path | None" = None) -> int:
    from ..core import config
    return int(config.get(
        "dispatch.intake_timeout_sec", default=300,
        env_var="ASTERISM_INTAKE_TIMEOUT_SEC", cast=int,
        workspace=workspace))


def run_intake(*, prompt_dir: Path, attempts_dir: Path,
               problem_dir: Path, label: str,
               workspace: "Path | None" = None) -> IntakeOutcome:
    """Spawn the intake turn and parse its sentinel. `label` is a short
    goal/brief identifier for log lines. Caller must have compiled
    Context.md into `attempts_dir` first (the cold-prompt wrapper
    points the agent at it)."""
    sid = str(uuid.uuid4())
    sentinel = attempts_dir / _SENTINEL
    try:
        sentinel.unlink()
    except OSError:
        pass
    rc = agent.spawn_llm(
        kind="formalizer",
        prompt_path=prompt_dir / "formalizer" / "intake.md",
        problem_dir=problem_dir,
        attempts_dir=attempts_dir,
        session_id=sid,
        timeout_sec_override=intake_timeout_sec(workspace),
    )
    if rc in INTAKE_INFRA_RCS:
        return IntakeOutcome(infra_rc=rc)
    if rc != 0:
        print(f"[intake] {label}: spawn rc={rc} — degrading to classic "
              f"cold flow", flush=True)
        return IntakeOutcome(sid=None)
    try:
        data = json.loads(sentinel.read_text(encoding="utf-8"))
        verdict = str(data.get("verdict", "")).strip().lower()
    except (OSError, ValueError):
        print(f"[intake] {label}: sentinel missing/unparseable — "
              f"proceeding (economy gate, fail-open)", flush=True)
        return IntakeOutcome(sid=sid)
    if verdict == "decline":
        reason = str(data.get("reason", "")).strip()
        note = str(data.get("note", "")).strip()
        if reason not in _VALID_DECLINE_REASONS:
            # Pre-#124 this coerced to the return-to-NL reason — a one-word
            # vocabulary's fail-safe. With two reasons a coercion is a
            # mislabel; the work turn carries the full vocabulary.
            print(f"[intake] {label}: unknown decline reason {reason!r} "
                  f"— proceeding (work turn has the full vocabulary)",
                  flush=True)
            return IntakeOutcome(sid=sid)
        if reason == "unprovable" and not note:
            # The bar is a concrete counterexample; a bare verdict fails
            # open rather than flipping a goal to disproved on a hunch.
            print(f"[intake] {label}: unprovable without a counterexample "
                  f"note — proceeding", flush=True)
            return IntakeOutcome(sid=sid)
        return IntakeOutcome(declined=(reason, note or "(no note)"))
    if verdict != "proceed":
        print(f"[intake] {label}: unknown verdict {verdict!r} — "
              f"proceeding (economy gate, fail-open)", flush=True)
    return IntakeOutcome(sid=sid)
