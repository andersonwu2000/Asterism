"""Mechanical ingest of failure knowledge into the KB as antipattern entries.

No LLM: the source material — agent-authored `.drafts` progress notes and
`dead_attempts` decline rationale — is already distilled prose; we only reshape
it into title+body antipattern entries. Idempotent: each run rebuilds the
ingested antipatterns (provenance `ingest:*`), leaving reflection lessons and
any other entries untouched.

Sources (Phase 12 design §4 — "按極性拆"; only the confirmed-negative pieces):
  * `.drafts/<kind>_g<gid>.md` — the `blocker` section (with `approach` as
    context). The most consistent source (~86% of notes carry a blocker).
  * `dead_attempts` decline rationale — `proposal_md` for the knowledge-bearing
    decline reasons (agent_shelved / parent_needs_fix / agent_infeasible).
  * `dead_attempts` embedded blocker — the lean error in `agent_stuck_thinking`
    `failure_detail`.
A note's `alternative` (an unverified next-attempt guess) is NOT ingested.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from . import db

_TITLE_CAP = 160
_DECLINE_REASONS = ("agent_shelved", "parent_needs_fix", "agent_infeasible")
_DRAFTS_RE = re.compile(r"(?:builder|backward)_g(\d+)\.md$")
_HEADER_RE = re.compile(r"^#{1,4}\s+(.+?)\s*$")
_ERROR_RE = re.compile(r"error:\s*([^;]+)")
_DIAG_RE = re.compile(
    r"([^\n]*\b(?:WRONG|FALSE|cannot|can't|blocks?|impossible|unprovable|"
    r"no existing|missing)\b[^\n]*)", re.I)
# Bare section-header labels from the decline / progress-note templates — never
# informative as a title (the substance is the prose underneath).
_GENERIC_LABELS = frozenset({
    "counterexample", "fix hint", "why unprovable as stated",
    "missing vocabulary", "missing piece", "what works now",
    "remaining work", "next dispatch action", "status", "proof approach",
})


def _parse_sections(text: str) -> dict[str, str]:
    """Map lower-cased `## header` → section body. Tolerates the agent-authored
    label drift (numbered headers, synonyms) and missing sections."""
    sections: dict[str, str] = {}
    cur: str | None = None
    buf: list[str] = []
    for ln in text.splitlines():
        m = _HEADER_RE.match(ln)
        if m:
            if cur is not None:
                sections[cur] = "\n".join(buf).strip()
            cur = m.group(1).strip().lower()
            buf = []
        elif cur is not None:
            buf.append(ln)
    if cur is not None:
        sections[cur] = "\n".join(buf).strip()
    return sections


def _first_line(text: str, cap: int = _TITLE_CAP, substantive: int = 20) -> str:
    """First *substantive* line for a title: skips bare section-header labels
    (`## Counterexample`, `## Fix hint`) and framework metadata (`entry_kind:`),
    preferring the first line long enough to carry meaning; falls back to the
    first non-empty line when none qualifies."""
    first: str | None = None
    for ln in text.splitlines():
        s = ln.strip().lstrip("#").strip()
        if not s or s.lower().startswith("entry_kind:"):
            continue
        if s.lower().rstrip(":").strip() in _GENERIC_LABELS:
            continue  # known section label — never a useful title
        if first is None:
            first = s
        if len(s) >= substantive:
            return s[:cap]
    return first[:cap] if first else ""


def _drafts_antipattern(text: str) -> tuple[str, str] | None:
    """(title, body) from a progress note, or None if it carries no blocker."""
    secs = _parse_sections(text)
    blocker = next((v for k, v in secs.items() if "blocker" in k), "")
    title = _first_line(blocker)
    if not blocker or not title:
        return None
    approach = next(
        (v for k, v in secs.items()
         if "approach" in k or "shape" in k or "converging" in k), "")
    body = ("Approach: " + approach + "\n" if approach else "") + \
           "Blocker: " + blocker
    return title, body.strip()


def _clean_decline(md: str) -> tuple[str, str]:
    """(title, body) from a `-- decline:`-style proposal_md comment block."""
    cleaned: list[str] = []
    for ln in md.splitlines():
        s = ln.strip()
        if s.startswith("--"):
            s = s[2:].strip()
        if s.lower().startswith("decline:"):
            continue
        cleaned.append(s)
    body = "\n".join(cleaned).strip()
    return _first_line(body), body


def _stuck_blocker(detail: str) -> tuple[str, str] | None:
    """(title, body) from an agent_stuck_thinking failure_detail (carries the
    real lean error inline)."""
    m = _ERROR_RE.search(detail)
    if not m:
        return None
    return m.group(1).strip()[:_TITLE_CAP], detail.strip()


def _noop_diagnosis(detail: str) -> tuple[str, str] | None:
    """(title, body) ONLY when a strategist_noop carries a real diagnosis
    (WRONG / FALSE / unprovable / …). Most noop rows are operational narration
    ('routine tick', 'first_launch', 'batch resolved success') — no antipattern,
    so they are skipped (no first-line fallback)."""
    m = _DIAG_RE.search(detail)
    if not m:
        return None
    return m.group(1).strip()[:_TITLE_CAP], detail.strip()


_KNOWLEDGE_REASONS = _DECLINE_REASONS + ("agent_stuck_thinking",
                                         "strategist_noop")


def _insert_antipattern(conn: sqlite3.Connection, *, title: str, body: str,
                        problem: str, node_id: int | None,
                        provenance: str) -> int:
    """Idempotent insert keyed on `provenance` (a stable per-source ref like
    `da:<id>` / `drafts:g<gid>`), so live capture and the batch rebuild never
    double-insert the same source. No commit. Returns 1 if inserted, 0 if the
    source was already captured."""
    cur = conn.execute(
        "INSERT INTO kb_entries"
        " (type, title, body, problem, node_id, scope, provenance, created_at)"
        " SELECT 'antipattern', ?, ?, ?, ?, 'node', ?, ?"
        " WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE provenance = ?)",
        (title, body, problem, node_id, provenance, db.now(), provenance),
    )
    return cur.rowcount


def capture_dead_attempt(conn: sqlite3.Connection, *, da_id: int,
                         target_id: int, target_kind: str, reason: str,
                         detail: str = "", proposal_md: str = "") -> int:
    """Capture the antipattern for ONE dead_attempt if its reason is
    knowledge-bearing (decline rationale / embedded blocker / noop diagnosis).
    Shared by the live hook (`db.record_dead_attempt`) and the batch rebuild.
    No-op for non-Goal targets or non-knowledge reasons. No commit."""
    if target_kind != "Goal":
        return 0
    parsed: tuple[str, str] | None = None
    if reason in _DECLINE_REASONS and (proposal_md or "").strip():
        parsed = _clean_decline(proposal_md)
    elif reason == "agent_stuck_thinking":
        parsed = _stuck_blocker(detail or "")
    elif reason == "strategist_noop":
        parsed = _noop_diagnosis(detail or "")
    if not parsed or not parsed[0]:
        return 0
    row = conn.execute(
        "SELECT problem FROM goals WHERE id = ?", (target_id,)).fetchone()
    if row is None:
        return 0  # Forward (target_id=0) / stale gid — no node to mount on
    return _insert_antipattern(conn, title=parsed[0], body=parsed[1],
                               problem=row["problem"], node_id=target_id,
                               provenance=f"da:{da_id}")


def capture_drafts(conn: sqlite3.Connection, *, path: Path, gid: int) -> int:
    """Capture the blocker antipattern from ONE `.drafts` note. Shared by the
    live hook (`persist_partials`) and the batch rebuild. No commit."""
    row = conn.execute(
        "SELECT problem FROM goals WHERE id = ?", (gid,)).fetchone()
    if row is None:
        return 0  # stale gid (goal gone) — skip
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    parsed = _drafts_antipattern(text)
    if parsed is None:
        return 0
    # Key on the note FILE (`<kind>_g<gid>`), not the goal — a goal can have
    # both a builder and a backward note carrying distinct blockers.
    return _insert_antipattern(conn, title=parsed[0], body=parsed[1],
                               problem=row["problem"], node_id=gid,
                               provenance=f"drafts:{Path(path).stem}")


def _ingest_drafts(conn: sqlite3.Connection, workspace: Path) -> int:
    n = 0
    for path in sorted((workspace / "Problems").glob("**/.drafts/*.md")):
        m = _DRAFTS_RE.match(path.name)
        if m:
            n += capture_drafts(conn, path=path, gid=int(m.group(1)))
    return n


def _ingest_dead_attempts(conn: sqlite3.Connection) -> int:
    ph = ",".join("?" * len(_KNOWLEDGE_REASONS))
    n = 0
    for r in conn.execute(
        "SELECT id, target_id, target_kind, failure_reason, failure_detail,"
        f" proposal_md FROM dead_attempts WHERE failure_reason IN ({ph})",
        _KNOWLEDGE_REASONS,
    ):
        n += capture_dead_attempt(
            conn, da_id=r["id"], target_id=r["target_id"],
            target_kind=r["target_kind"], reason=r["failure_reason"],
            detail=r["failure_detail"], proposal_md=r["proposal_md"])
    return n


def ingest_antipatterns(conn: sqlite3.Connection, workspace: Path) -> int:
    """Batch backfill / repair: capture every failure source's antipattern,
    idempotently (source-keyed). Additive — safe to re-run and to coexist with
    live capture (`capture_*`, also called from the failure write-paths). The
    one-time `ingest:%` delete migrates rows from before the source-keyed
    provenance scheme. Returns the number newly inserted."""
    conn.execute(
        "DELETE FROM kb_entries WHERE type = 'antipattern'"
        " AND provenance LIKE 'ingest:%'")  # legacy-scheme migration (one-time)
    n = _ingest_drafts(conn, workspace) + _ingest_dead_attempts(conn)
    conn.commit()
    return n
