"""Agent framework-feedback sink — developer-only writeback.

A dev-mode channel for the framework developer to hear, from the agents
that worked inside the framework, what to improve. Two entry kinds land
in ONE file (`.asterism/agent_feedback.md`, gitignored):

  1. Agent-filed note — the `feedback(note, evidence)` MCP tool
     (`knowledge/mcp_tools.py`), called BY THE AGENT the moment something
     misleads it, mid-run. `record_note` below is the writer.

  2. Death-cause auto-write — an agent that died without a resumable
     session (the infra reasons `_retry.py` skips reflection for:
     spawn_fast_fail / quota_exhausted / missing_dep) can't file
     anything, so the framework writes its death cause directly. Closes
     the selection bias: the worst experiences would otherwise be
     invisible, and a spawn that died mid-tool-call filed nothing.

WHY MID-RUN AND NOT AT THE TAIL (owner ruling 2026-09-07). The channel
used to be an end-of-run questionnaire: every finished spawn was resumed
for one extra leg (`attempt_feedback`) and asked to write one sentence
into its sandbox. That leg was retired. It cost a spawn per pipeline; it
reached only agents that survived to a resumable terminal; and it asked
at the one moment the friction is furthest away — an agent looking back
at a finished task reconstructs its complaint, where a tool called at the
moment a gate refuses on a false premise carries the refusal verbatim.

The framework still owns the metadata prefix
`[ts | kind | model | outcome | problem/slug]` and the (globally-locked)
append, so concurrent spawns across different problems never corrupt the
file: the agent supplies one sentence, never a line of the record.

Off by default. Enable with `feedback.enabled: true` in Asterism.yaml (or
`ASTERISM_FEEDBACK_ENABLED=true`). The same gate decides whether the seat
prompts ADVERTISE the tool (`agent/runtime` renders the `feedback_tool`
conditional block from it) — outside developer mode the tool exists but
no prompt spends an agent's attention on it. The output file lives under
the gitignored `.asterism/` runtime-state tree, so a shared framework
checkout neither has it nor triggers it, and
`envelope.PRIVATE_READ_SUBTREES` already denies every spawn read access
to it.
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from pathlib import Path

#: Owner ruling 2026-09-06: the private docs tree moved to its own
#: repository, so production must never write into `docs/internal/`. This
#: sink is runtime state, so it lives with the rest of it under
#: `.asterism/` — gitignored, and already a spawn read-deny root.
_FEEDBACK_REL = ".asterism/agent_feedback.md"

#: What starts a record. The ring trim below counts in these units, and
#: so does anything else that asks how much this file holds — a second
#: spelling of the marker would drift the first time the prefix changes.
RECORD_MARK = "- ["

#: What the `outcome` column says for a note filed by a running agent.
#: The column has always answered "how did this spawn end", and a mid-run
#: record has no answer to that yet — writing `success` there would date
#: a complaint to an outcome nobody has seen.
IN_FLIGHT = "in-flight"

#: Ring cap (owner call 2026-08-29): feedback is short-shelf-life signal —
#: entries go stale against the moving code (triage re-verifies every claim
#: anyway) and the durable layers (backlog items, adjudications, commits)
#: hold whatever mattered. An unattended long run must not grow this file
#: without bound, so the write chokepoint keeps only the newest N whole
#: records — no cron, no operator memory involved.
MAX_ENTRIES = 1000

_HEADER = (
    "# Agent framework feedback (dev-only)\n\n"
    "_Agent-filed notes + framework-written death causes. One line each:_\n"
    "_`- [ts | kind | model | outcome | problem/slug] <sentence>`_\n"
    "_(+ optional `  evidence: ...` continuation). Newest at the bottom;_\n"
    f"_a ring — only the newest {MAX_ENTRIES} records are kept._\n\n"
)

# Single global lock: the output is ONE shared file across all problems, so
# (unlike LESSONS.md's per-problem lock) appends from concurrent spawns must
# serialize globally. Held only for the fast file append, never across an
# LLM call.
_APPEND_LOCK = threading.Lock()


def feedback_path(workspace: Path) -> Path:
    """The shared feedback file for a workspace — the ONE place its
    location is spelled.

    A lab run's workspace is deleted when the run ends, so `lab/driver`
    copies this file into `_out/` before that happens; without a name to
    ask for, that copier would carry a second spelling of the path and
    rot the first time this one moves. It has moved once already (owner
    ruling 2026-09-06, out of `docs/internal/`)."""
    return Path(workspace) / _FEEDBACK_REL


def count_records(text: str) -> int:
    """How many whole records a feedback file's text holds.

    The count the lab reports, and the unit the ring trims in: a record
    is a `RECORD_MARK` line plus whatever indented continuation lines
    follow it, so counting LINES would double every entry that carries
    an `evidence:` line."""
    return sum(1 for ln in text.splitlines() if ln.startswith(RECORD_MARK))


def _trim_locked(path: Path) -> None:
    """Drop the oldest records past `MAX_ENTRIES`, in WHOLE-record units
    (a `- [` line plus its indented continuation lines); the header block
    above the first record is preserved verbatim. Runs under
    `_APPEND_LOCK`, right after an append; atomic replace so a crash
    mid-trim cannot eat the file."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    starts = [i for i, ln in enumerate(lines) if ln.startswith(RECORD_MARK)]
    if len(starts) <= MAX_ENTRIES:
        return
    keep_from = starts[len(starts) - MAX_ENTRIES]
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(lines[:starts[0]]) + "".join(lines[keep_from:]),
                   encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def feedback_enabled(workspace: Path | None) -> bool:
    """Read `feedback.enabled` from Asterism.yaml / env. Defaults to
    FALSE — this is a developer-only channel, off unless explicitly turned
    on. Accepts "true" / "1" / "yes" / "on" (case-insensitive)."""
    from ..core import config
    raw = config.get("feedback.enabled", workspace=workspace)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("true", "1", "yes", "on")


def _resolve_model(kind: str, workspace: Path | None) -> str:
    """The configured model string for `kind` (for the metadata prefix).
    Best-effort: returns '?' if unresolvable."""
    from ..core import config
    try:
        m = config.get(f"{kind.lower()}.model", workspace=workspace)
        return str(m) if m else "?"
    except Exception:  # noqa: BLE001 — metadata is best-effort
        return "?"


def _append(workspace: Path, line: str) -> bool:
    """Globally-locked append of one record to the shared feedback file,
    creating it (with header) on first write. Best-effort: any error is
    swallowed — feedback must never block or fail the dispatcher.

    Returns whether the record landed. The framework-written callers
    ignore it; the agent-facing tool does not — an acknowledgement that
    says "filed" for a write that failed teaches the agent the channel
    works when it does not."""
    path = feedback_path(workspace)
    try:
        with _APPEND_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(_HEADER, encoding="utf-8")
            with path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(line if line.endswith("\n") else line + "\n")
            _trim_locked(path)
    except OSError:
        return False
    return True


def _now_minute() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def _prefix(*, kind: str, model: str, outcome: str, problem: str,
            slug: str) -> str:
    return (f"- [{_now_minute()} | {kind} | {model} | {outcome} | "
            f"{problem}/{slug}] ")


def _one_line(text: str, limit: int) -> str:
    """Flatten agent-authored text to one bounded line.

    A record is ONE line and `count_records` counts `RECORD_MARK` lines,
    so a note carrying a newline would split into two records, the
    second of which is not one. A tool-call argument is text of any
    shape, so the flattening happens here, at the writer, rather than
    being asked of every caller."""
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[:limit].rstrip() + " …"


#: How much of one record the agent may write. Not politeness: the ring
#: keeps the newest `MAX_ENTRIES` RECORDS, so one spawn pasting a whole
#: tool dump evicts other spawns' sentences by volume. A sentence and a
#: line of evidence fit inside these; a transcript does not.
MAX_NOTE_CHARS = 400
MAX_EVIDENCE_CHARS = 600


def record_note(workspace: Path | None, *, kind: str, slug: str,
                problem: str, note: str, evidence: str = "",
                outcome: str = IN_FLIGHT,
                seat: "str | None" = None) -> bool:
    """Append ONE agent-filed record. Returns whether it landed.

    The writer behind the `feedback(note, evidence)` MCP tool. The agent
    supplies `note` (and optionally `evidence`); every other column is
    the framework's, resolved from the spawn's own identity by the
    caller. Returns False — never raises — when feedback is disabled,
    the note is empty, or the append failed, so the tool's
    acknowledgement can say which.

    The MODEL is a property of the seat, not of the label: there is no
    `forward.model` or `cleanup:audit.model` key, so resolving from the
    label wrote `?` into every such record (2026-08-13). Callers that
    only ever label (`record_death`, the record-shape tests) pass no
    seat and keep the old reading."""
    if not feedback_enabled(workspace) or workspace is None:
        return False
    first = _one_line(note, MAX_NOTE_CHARS)
    if not first:
        return False
    rec = _prefix(kind=kind, model=_resolve_model(seat or kind, workspace),
                  outcome=outcome, problem=problem, slug=slug) + first
    ev = _one_line(evidence, MAX_EVIDENCE_CHARS)
    if ev:
        # Same continuation shape the file has always carried, so
        # `count_records` still counts this as ONE record.
        rec += "\n  evidence: " + ev
    return _append(workspace, rec)


def record_death(workspace: Path | None, *, kind: str, slug: str,
                 problem: str, reason: str) -> None:
    """Framework-written death cause for an agent that died without a
    resumable session (so it could file nothing itself). No-op when
    disabled. The `(dead)` outcome marker distinguishes these from
    agent-filed notes."""
    if not feedback_enabled(workspace) or workspace is None:
        return
    rec = _prefix(kind=kind, model=_resolve_model(kind, workspace),
                  outcome="(dead)", problem=problem, slug=slug)
    _append(workspace, rec + f"DIED: {reason} (no resumable session — "
            f"framework-written, agent could not self-report)")
