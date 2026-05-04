"""F26 — companion reference files written into the attempts dir.

Context.md is the agent's primary briefing — must stay tight to keep
attention focused on the goal at hand. Bulky / on-demand information
(full lake stderr from prior failures, prior PROPOSAL.md texts,
Verify-failure histories) lives here, in side files the agent can
read via its `--add-dir` permission when the Context.md summary
isn't enough.

Read pattern:
- Agent always reads Context.md (mandatory primary briefing)
- Agent reads `PAST_ATTEMPTS.md` etc. only when the summary's digest
  doesn't suffice (e.g. recurring same-shape error needs raw stderr
  to spot the exact type-mismatch detail).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from . import diagnostics


PAST_ATTEMPTS_FILENAME = "PAST_ATTEMPTS.md"
# F55 — formerly PAST_VERIFIES.md; renamed to cover the broader "past
# Backward work" semantics, which now also includes the prior partial
# PROPOSAL.md draft from a failed / timed-out attempt.
PAST_BACKWARD_FILENAME = "PAST_BACKWARD.md"

# F30 — companion files are the lazy-load deeper-look reference, but
# raw lake stderr still carries 1.5+ KB LEAN_PATH dump per attempt.
# When the agent does pull these files, every byte matters. Reuse
# diagnostics.smart_truncate_stderr to surface error/warning lines
# first; budget is wider than Context.md's inline cap (2000) since
# this is by-design the deeper reference file.
_COMPANION_STDERR_BUDGET = 4000


def render_attempt_block(idx: int, dead: sqlite3.Row) -> str:
    """Per-attempt section: failure_reason header + smart-truncated
    failure_detail + (optional) raw proposal_md."""
    lines: list[str] = []
    lines.append(
        f"### Attempt {idx} ({dead['pipeline_id'][:12]}): "
        f"{dead['failure_reason']}"
    )
    if dead["failure_detail"]:
        truncated = diagnostics.smart_truncate_stderr(
            dead["failure_detail"], budget=_COMPANION_STDERR_BUDGET,
            force_reorder=True)
        lines.extend(["", "```", truncated, "```"])
    if dead["proposal_md"]:
        # proposal_md is the agent's own prose (PROPOSAL.md) — no
        # lake noise to strip. Include verbatim.
        lines.extend(["", "Strategy summary (from PROPOSAL.md):",
                      "```", dead["proposal_md"], "```"])
    lines.append("")
    return "\n".join(lines)


def write_past_attempts(deads: Iterable[sqlite3.Row],
                        attempts_dir: Path) -> Path | None:
    """Write `PAST_ATTEMPTS.md` with the full per-dead-attempt history
    for THIS goal. No-op (returns None) when `deads` is empty."""
    rows = list(deads)
    if not rows:
        return None
    parts: list[str] = [
        "# Full failure history for this goal",
        "",
        "Context.md shows a 1-line digest per attempt; this file is the "
        "raw failure_detail + originating PROPOSAL.md, in case the digest "
        "doesn't surface enough to diagnose a recurring error. Most "
        "recent attempt first.",
        "",
    ]
    for i, d in enumerate(rows, 1):
        parts.append(render_attempt_block(i, d))
    out = attempts_dir / PAST_ATTEMPTS_FILENAME
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


def render_strategy_block(idx: int, row: sqlite3.Row) -> str:
    """Per-Verify-failure section. Same smart-truncate treatment as
    render_attempt_block (F30)."""
    lines: list[str] = []
    lines.append(
        f"### Strategy {idx} (pid {row['pipeline_id'][:12]}): "
        f"{row['failure_reason']}"
    )
    if row["failure_detail"]:
        truncated = diagnostics.smart_truncate_stderr(
            row["failure_detail"], budget=_COMPANION_STDERR_BUDGET,
            force_reorder=True)
        lines.extend(["", "```", truncated, "```"])
    if row["strategy_proposal"]:
        lines.extend(["", "Decomposition (from strategies.proposal_md):",
                      "```", row["strategy_proposal"], "```"])
    lines.append("")
    return "\n".join(lines)


def write_past_backward(strat_deads: Iterable[sqlite3.Row],
                        attempts_dir: Path) -> Path | None:
    """Write `PAST_BACKWARD.md` (F55 rename of PAST_VERIFIES.md) with
    the full Verify-failure history for sibling strategies on THIS
    goal. No-op when `strat_deads` is empty.

    F55 design note: the postmortem progress note from a prior
    timed-out spawn lives ONLY in Context.md's inline section
    (`_section_prior_partial`), not here — agents reliably miss
    companion files (F43 lesson), so the must-see channel is the
    inline render, and this companion stays narrowly scoped to
    "verify failure forensics"."""
    rows = list(strat_deads)
    if not rows:
        return None
    parts: list[str] = [
        "# Past decomposition Verify failures for this goal",
        "",
        "Earlier Backward attempts decomposed this goal but the "
        "combination patch did not elaborate against the sub-goal "
        "proofs. Each block is the raw lake stderr + the strategy's "
        "PROPOSAL.md.",
        "",
    ]
    for i, r in enumerate(rows, 1):
        parts.append(render_strategy_block(i, r))
    out = attempts_dir / PAST_BACKWARD_FILENAME
    out.write_text("\n".join(parts), encoding="utf-8")
    return out
