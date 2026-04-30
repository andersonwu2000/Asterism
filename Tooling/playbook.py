"""F22 — per-problem playbook of agent-curated success idioms.

Asymmetry the playbook closes: today's framework spends heavy
machinery preventing repeat *mistakes* (dead_attempts → Context.md)
but loses every *win* the moment it's committed to git. A sub-goal
proved by a clever ZMod bridge in wilson teaches nothing to tomorrow's
Haiku attempt at cantor — the idiom dies with the strategy.

This module captures successful strategy idioms in a per-problem file
`Problems/<p>/playbook.md`, which compile_context injects into future
agent runs. The playbook self-curates: when the file hits CAP entries,
a follow-up LLM call must either choose an entry to evict OR explicitly
KEEP existing entries (declining the new candidate). FIFO would
mechanically discard wisdom; agent-curated eviction makes quality
monotone non-decreasing under the agent's own judgment.

Failures (LLM unreachable, malformed reply, file IO) are swallowed and
never block the dispatcher — playbook is enrichment, not load-bearing.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import llm


PLAYBOOK_FILENAME = "playbook.md"
PLAYBOOK_CAP = 10
EXTRACT_TIMEOUT_SEC = 60
CURATE_TIMEOUT_SEC = 60

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_EXTRACT_PROMPT_PATH = _PROMPTS_DIR / "playbook_extract.md"
_CURATE_PROMPT_PATH = _PROMPTS_DIR / "playbook_curate.md"


@dataclass(frozen=True)
class CurationResult:
    """Outcome of a curation attempt. `replaced_index` is set only when
    action == 'replaced'."""
    action: str
    replaced_index: int | None = None


def _path_for(problem: str, workspace: Path) -> Path:
    return workspace / "Problems" / problem / PLAYBOOK_FILENAME


def read_playbook(problem: str, workspace: Path) -> str:
    """Return playbook.md raw text or empty string if file absent."""
    p = _path_for(problem, workspace)
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def parse_entries(text: str) -> list[str]:
    """Split playbook text into bullet entries. An entry begins at
    ``- `` at column 0 and continues through indented / blank lines
    until the next bullet or EOF."""
    if not text.strip():
        return []
    lines = text.splitlines()
    entries: list[str] = []
    current: list[str] = []
    for ln in lines:
        if ln.startswith("- "):
            if current:
                entries.append("\n".join(current).rstrip())
            current = [ln]
        elif current and ln.strip() == "":
            current.append(ln)
        elif current:
            # Indented continuation
            current.append(ln)
    if current:
        entries.append("\n".join(current).rstrip())
    # Drop trailing blank-only entries
    return [e for e in entries if e.strip()]


def _normalize_candidate(raw: str) -> str | None:
    """Coerce LLM reply into a single-bullet entry of ≤3 lines.
    Returns None when the reply doesn't contain a bullet (or signals
    SKIP).
    """
    if not raw:
        return None
    text = raw.strip()
    if text == "SKIP":
        return None
    if text.startswith("- "):
        candidate = text
    else:
        # Fish out the first bullet anywhere in the response
        m = re.search(r"^- .*$", text, re.MULTILINE)
        if not m:
            return None
        candidate = text[m.start():]
    # Cap at 3 lines starting from the bullet
    lines = candidate.splitlines()[:3]
    return "\n".join(lines).rstrip()


def extract_idiom(
    strategy_id: int, conn: sqlite3.Connection, workspace: Path,
) -> str | None:
    """Spawn a short LLM call asking for a one-bullet idiom summary
    of the just-proven strategy. Returns the candidate entry text or
    None when the LLM is unavailable / signals SKIP / replies in an
    un-parseable form."""
    row = conn.execute(
        "SELECT s.proposal_md, s.scratch_path, s.goal_id, g.statement "
        "FROM strategies s JOIN goals g ON g.id = s.goal_id "
        "WHERE s.id = ?", (strategy_id,),
    ).fetchone()
    if not row:
        return None
    proof_text = ""
    scratch = workspace / row["scratch_path"] if row["scratch_path"] else None
    if scratch and scratch.exists():
        try:
            proof_text = scratch.read_text(encoding="utf-8")
        except OSError:
            proof_text = ""
    try:
        prompt = _EXTRACT_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return None
    prompt = prompt.replace("{{GOAL_STATEMENT}}", row["statement"] or "")
    prompt = prompt.replace("{{PROPOSAL}}",
                            (row["proposal_md"] or "")[:1500])
    prompt = prompt.replace("{{PROOF}}", proof_text[:3000])

    reply = llm.get_provider().complete_text(
        prompt=prompt, timeout_sec=EXTRACT_TIMEOUT_SEC,
    )
    return _normalize_candidate(reply or "")


def _atomic_write(path: Path, content: str) -> None:
    """Write whole-file atomically: temp + replace. Avoids torn writes
    if a concurrent reader is mid-load."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _format_playbook(entries: list[str]) -> str:
    if not entries:
        return ""
    return "\n\n".join(entries) + "\n"


def curate_and_write(
    problem: str, candidate: str, workspace: Path,
) -> CurationResult:
    """Append candidate when under cap; else ask the LLM whether to
    REPLACE n or KEEP. Malformed / missing replies fall back to KEEP
    so a flaky LLM never pollutes the playbook."""
    p = _path_for(problem, workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    entries = parse_entries(read_playbook(problem, workspace))

    if len(entries) < PLAYBOOK_CAP:
        entries.append(candidate)
        _atomic_write(p, _format_playbook(entries))
        return CurationResult(action="appended")

    # At cap — let the agent decide
    try:
        prompt = _CURATE_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return CurationResult(action="kept_existing")
    listing = "\n".join(f"{i + 1}. {e}" for i, e in enumerate(entries))
    prompt = prompt.replace("{{EXISTING}}", listing)
    prompt = prompt.replace("{{CANDIDATE}}", candidate)
    reply = llm.get_provider().complete_text(
        prompt=prompt, timeout_sec=CURATE_TIMEOUT_SEC,
    )
    if not reply:
        return CurationResult(action="kept_existing")
    decision = reply.strip().splitlines()[0].strip().upper()
    if decision == "KEEP":
        return CurationResult(action="kept_existing")
    m = re.match(r"REPLACE\s+(\d+)", decision)
    if m:
        try:
            n = int(m.group(1))
        except ValueError:
            return CurationResult(action="kept_existing")
        if 1 <= n <= len(entries):
            entries[n - 1] = candidate
            _atomic_write(p, _format_playbook(entries))
            return CurationResult(action="replaced", replaced_index=n)
    # Any other phrasing: conservative fallback
    return CurationResult(action="kept_existing")


def maybe_record_idiom(
    strategy_id: int, conn: sqlite3.Connection, workspace: Path,
) -> CurationResult | None:
    """Hook called from cascade_one when a Verify proves a strategy.
    Best-effort: any failure (LLM unreachable, file IO, candidate
    rejected) is swallowed and logged. Never raises."""
    try:
        candidate = extract_idiom(strategy_id, conn, workspace)
        if not candidate:
            return None
        # Resolve problem name from strategy → goal
        row = conn.execute(
            "SELECT g.problem FROM strategies s "
            "JOIN goals g ON g.id = s.goal_id WHERE s.id = ?",
            (strategy_id,),
        ).fetchone()
        if not row:
            return None
        result = curate_and_write(row["problem"], candidate, workspace)
        print(f"[playbook] strategy={strategy_id} {result.action}"
              + (f" (replaced #{result.replaced_index})"
                 if result.replaced_index else ""), flush=True)
        return result
    except Exception as exc:  # never block the dispatcher
        print(f"[playbook] strategy={strategy_id} failed: {exc}",
              flush=True)
        return None
