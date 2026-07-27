"""Formalizer intake stage (update_plan_2026_07 #1).

First turn on a fresh session: the agent reads Context.md (Programme
`## Proof` + assignment + tree state) and writes an `intake.json`
sentinel — `{"verdict":"proceed"}` or
`{"verdict":"decline","reason":"no_nl_correspondence","note":...}`.

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
_VALID_DECLINE_REASONS = ("no_nl_correspondence",)


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


def intake_timeout_sec() -> int:
    from ..core import config
    return int(config.get(
        "dispatch.intake_timeout_sec", default=300,
        env_var="ASTERISM_INTAKE_TIMEOUT_SEC", cast=int))


def run_intake(*, prompt_dir: Path, attempts_dir: Path,
               problem_dir: Path, label: str) -> IntakeOutcome:
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
        timeout_sec_override=intake_timeout_sec(),
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
        if reason not in _VALID_DECLINE_REASONS:
            reason = _VALID_DECLINE_REASONS[0]
        note = str(data.get("note", "")).strip() or "(no note)"
        return IntakeOutcome(declined=(reason, note))
    if verdict != "proceed":
        print(f"[intake] {label}: unknown verdict {verdict!r} — "
              f"proceeding (economy gate, fail-open)", flush=True)
    return IntakeOutcome(sid=sid)
