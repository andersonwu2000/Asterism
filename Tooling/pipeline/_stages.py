"""The Formalizer's stage chain, in one place.

`update_plan_2026_07.md` §1 ratified ONE chain, with the stations fixed
and only the middle enabled by decision shape:

    _intake ──[presearch]──> ( _forward ──[commit] )? ──> _formalize …

The chain lived in the design doc and in two hand-written sequences —
`forward.py`'s mint block and `backward.py`'s goal block — which is how
a station could be missing from one arm and nobody notice. On 2026-07-27
a code reviewer reported exactly that ("mint-job work turn is promised
presearch candidates that are never produced") and named both repairs:
wire the station, or edit the prompts that promise it. The prompt edit
shipped, because with two sequences it was the cheap one — the capability
gap survived under a CONFIRMED finding, filed as a "prompt false
promise". THAT is the argument for this module: with one chain, "does the
mint arm run presearch?" is not a question anyone can answer wrong.

What lives here is the head of the chain — every station before the work
turn. The work turn itself is `_retry.run_lsp_edit_loop`, which already
owns the spawn ceremony and the retry ladder.

Load-bearing subtlety, and the second reason this is one function: after
intake succeeds the first work spawn is a CONTINUATION (`initial_sid`
set → `cold=False` → `_retry` SKIPS `cold_prep_fn`, see `_retry.py`'s
`_spawn`). So the context the work turn reads is whatever this chain
wrote — nothing downstream recompiles it. Presearch's whole point is to
land in that context, so the recompile after it is not tidiness, it is
the delivery. The mint arm had no recompile and would have silently
delivered nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — typing only
    from . import PipelineResult


@dataclass
class Arm:
    """What differs between the goal arm and the mint arm.

    Everything NOT in here is the chain, and the chain is identical.

    `decline_result` is a per-arm callable rather than a shared mapping
    on purpose: the goal arm routes an intake decline through
    `DECLINE_TO_FAILURE_REASON` (its reasons drive the cascade), while
    the mint arm renders the Forward decline shape (`agent_declined` +
    "agent declined (<kind>): why") because the Inject outcome stash
    downstream parses that text. Two real contracts, not drift.
    """

    #: for logs — "g123 slug" / "mint inject42 Problem"
    label: str
    #: write Context.md for the turn about to run
    compile_context: Callable[[], None]
    #: seed the LSP edit target (patch.lean / new_forward.lean)
    seed: Callable[[], None]
    #: run the arm's pre-search, keyed on whatever this arm has
    presearch: Callable[[], None]
    #: (reason, note) -> the arm's decline PipelineResult
    decline_result: Callable[[str, str], "PipelineResult"]
    #: optional early exit BEFORE the intake spawn spends anything.
    #: Goal-arm only, and that asymmetry is deliberate: goal jobs are
    #: dispatched by BFS and can race an over-budget goal, mints are
    #: dispatched by an Inject that carries a fresh budget by design.
    pre_intake_guard: Optional[Callable[[], "Optional[PipelineResult]"]] = None


def run_prework(arm: Arm, *, prompt_dir: Path, attempts_dir: Path,
                problem_dir: Path, workspace: Path,
                ) -> "tuple[Optional[PipelineResult], Optional[str]]":
    """Run the chain from its head up to the work turn.

    Returns `(result, intake_sid)`. A non-None `result` means the chain
    short-circuited (guard, infra, or decline) and the caller must NOT
    spawn the work turn. `intake_sid` is the session the work turn
    resumes; None means intake degraded and the work turn spawns cold —
    which is the pre-staging behaviour and always safe.

    Best-effort is deliberate at exactly one place: an intake
    malfunction must never block the work, only cost the cheap early
    exit. Every soundness gate lives in the commit path, not here.
    """
    from . import PipelineResult
    from ._intake import run_intake
    from ..llm.base import SpawnRC

    # Shared by both arms: an infra death is the framework's, not the
    # assignment's, so it must never be recorded against the goal.
    infra_map = {
        SpawnRC.SHUTDOWN: ("daemon_shutdown", "intake spawn aborted"),
        SpawnRC.MISSING_DEP: ("missing_dep", "intake spawn: CLI missing"),
        SpawnRC.QUOTA_EXHAUSTED: ("quota_exhausted",
                                  "intake spawn: quota / rate limit"),
    }

    if arm.pre_intake_guard is not None:
        guarded = arm.pre_intake_guard()
        if guarded is not None:
            return guarded, None

    # Context for the intake turn deliberately PREDATES presearch — a
    # declined assignment must not pay for the search.
    arm.compile_context()
    arm.seed()

    intake = run_intake(prompt_dir=prompt_dir, attempts_dir=attempts_dir,
                        problem_dir=problem_dir, workspace=workspace,
                        label=arm.label)

    if intake.infra_rc is not None:
        reason, detail = infra_map[intake.infra_rc]
        return PipelineResult(outcome="failed", failure_reason=reason,
                              failure_detail=detail), None

    if intake.declined is not None:
        reason, note = intake.declined
        print(f"[intake] {arm.label}: declined ({reason}) — {note[:160]}",
              flush=True)
        return arm.decline_result(reason, note), None

    # `proceed` — the search runs, then the context is rebuilt so the
    # work turn actually receives it (see the module docstring: the
    # continuation spawn skips cold-prep, so this is the only delivery).
    arm.presearch()
    arm.compile_context()
    return None, intake.sid
