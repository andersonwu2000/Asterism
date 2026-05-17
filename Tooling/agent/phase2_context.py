"""Phase 2 — Strategist + Forward Context.md compilation.

Strategist + Forward operate at problem-level, not goal-level — so
they bypass `compile_context` (which is hard-wired to a specific goal
row) and assemble Context.md from problem-level facts only.

Strategist sees:
  - `trigger_kind`
  - Active goal list with statements + status
  - Recent strategist_decisions + their outcomes (self-feedback)
  - TREE.md inline (precompiled artifact)
  - Manifest + Defs.lean (for T0 / T3)
  - Pending review target (for T2)

Forward sees:
  - Strategist brief (from queue.decision_id FK)
  - Library state (cross-problem proved lemmas)
  - TREE.md inline
  - Past Forward output history
  - Mathlib hints from Manifest (loogle is agent-driven via Bash tool)
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..state import db, manifest


# ---------------------------------------------------------------------
# Strategist
# ---------------------------------------------------------------------

def _section_trigger(trigger_kind: str, pending_review_id: int | None,
                     conn: sqlite3.Connection) -> list[str]:
    lines = [
        "## Trigger",
        "",
        f"`trigger_kind`: {trigger_kind}",
        "",
    ]
    if trigger_kind == "pending_review" and pending_review_id is not None:
        g = db.get_goal(conn, pending_review_id)
        if g is not None:
            lines += [
                f"Pending review on goal {pending_review_id}:",
                "",
                f"- slug: `{g['slug']}`",
                f"- statement: `{g['statement']}`",
                f"- depth: {g['depth']}",
                f"- attempts: {g['attempts']}",
                "",
            ]
    return lines


def _section_active_goals(conn: sqlite3.Connection,
                          problem: str) -> list[str]:
    rows = list(conn.execute(
        "SELECT id, slug, statement, depth, status, attempts"
        " FROM goals WHERE problem = ?"
        "   AND status IN ('open','attempting','pending_strategist_review')"
        " ORDER BY depth, id",
        (problem,),
    ))
    if not rows:
        return []
    out = ["## Active goals", ""]
    for r in rows:
        st = str(r["statement"])
        if len(st) > 200:
            st = st[:200].rstrip() + "…"
        out.append(
            f"- [{r['id']}] depth={r['depth']} "
            f"{r['status']:25s} attempts={r['attempts']}"
            f" `{r['slug']}`"
        )
        out.append(f"  `{st}`")
    out.append("")
    return out


def _section_failure_replay(conn: sqlite3.Connection,
                            problem: str,
                            k: int = 5) -> list[str]:
    """Last `k` strategist_decisions on this problem with their
    outcomes — self-feedback signal so Strategist learns
    'what I tried, what happened'."""
    try:
        rows = list(conn.execute(
            "SELECT triggered_at_tick, trigger_kind, decision_kind,"
            " target_id, brief, reason, payload, outcome, created_at"
            " FROM strategist_decisions WHERE problem = ?"
            " ORDER BY id DESC LIMIT ?",
            (problem, k),
        ))
    except sqlite3.OperationalError:
        return []
    if not rows:
        return ["## Recent decisions", "", "(none — first Strategist run)", ""]
    out = ["## Recent decisions (newest first)", ""]
    for r in rows:
        out.append(
            f"- tick={r['triggered_at_tick']} "
            f"trigger={r['trigger_kind']} → "
            f"`{r['decision_kind']}`"
            + (f" target={r['target_id']}" if r['target_id'] else "")
            + (f" outcome={r['outcome']}" if r['outcome'] else "")
        )
        if r["reason"]:
            reason = str(r["reason"])
            if len(reason) > 200:
                reason = reason[:200] + "…"
            out.append(f"  reason: {reason}")
        if r["brief"]:
            brief = str(r["brief"])
            if len(brief) > 200:
                brief = brief[:200] + "…"
            out.append(f"  brief: {brief}")
    out.append("")
    return out


def _section_tree_inline(workspace: Path, problem: str) -> list[str]:
    """Inline the problem's TREE.md (precompiled artifact). If absent
    (fresh problem post-init), return a stub note."""
    tree_path = db.problem_dir(workspace, problem) / "TREE.md"
    if not tree_path.exists():
        return ["## TREE", "", "(TREE.md not yet generated)", ""]
    try:
        text = tree_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ["## TREE", "", "(TREE.md unreadable)", ""]
    return ["## TREE", "", text, ""]


def _section_manifest_meta(mfst: manifest.Manifest,
                           workspace: Path, problem: str) -> list[str]:
    """For T0 / T3 — surface Manifest statement + hints + Defs.lean
    preview so Strategist can decide InitializeDefs / RequestUserAmend."""
    out = ["## Manifest", "", "### Statement", ""]
    out.append(f"```\n{mfst.statement}\n```")
    if mfst.all_hints:
        out += ["", "### Lemma hints", ""]
        for h in mfst.all_hints:
            out.append(f"- {h}")
    if mfst.strategic_notes:
        out += ["", "### Strategic notes", ""]
        out.append(mfst.strategic_notes)
    defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
    out += ["", "### Defs.lean", ""]
    if defs_path.exists():
        try:
            defs_text = defs_path.read_text(encoding="utf-8")
            out.append(f"```lean\n{defs_text}\n```")
        except OSError:
            out.append("(Defs.lean unreadable)")
    else:
        out.append("(Defs.lean does not exist — InitializeDefs candidate)")
    out.append("")
    return out


def compile_strategist_context(conn: sqlite3.Connection, *,
                               problem: str, trigger_kind: str,
                               attempts_dir: Path,
                               workspace: Path,
                               mfst: manifest.Manifest,
                               pending_review_id: int | None = None,
                               ) -> Path:
    """Write Context.md for the Strategist agent into attempts_dir.

    Sections (in order, all optional if their source is empty):
      - Trigger (always; includes pending review target for T2)
      - Active goals
      - Recent decisions (failure_replay)
      - TREE
      - Manifest (T0 / T3 — when bootstrap_done=false or amend-relevant)
    """
    sections: list[list[str]] = [
        _section_trigger(trigger_kind, pending_review_id, conn),
        _section_active_goals(conn, problem),
        _section_failure_replay(conn, problem),
        _section_tree_inline(workspace, problem),
        _section_manifest_meta(mfst, workspace, problem),
    ]
    parts: list[str] = [f"# Strategist context — {problem}", ""]
    for sect in sections:
        parts.extend(sect)
    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


# ---------------------------------------------------------------------
# Forward
# ---------------------------------------------------------------------

def _section_forward_brief(conn: sqlite3.Connection,
                           decision_id: int | None) -> list[str]:
    """Strategist Inject brief — primary input to Forward. Falls back
    to a placeholder if decision_id is None / row missing (shouldn't
    happen in production but tests / replay may exercise this)."""
    if decision_id is None:
        return [
            "## Strategist brief",
            "",
            "(no Strategist Inject brief — Forward was dispatched without one. "
            "Default to a broadly useful new lemma in the problem's domain.)",
            "",
        ]
    try:
        row = conn.execute(
            "SELECT brief FROM strategist_decisions WHERE id = ?",
            (int(decision_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row is None or not row["brief"]:
        return [
            "## Strategist brief",
            "",
            "(decision row missing brief content; treat as open-ended.)",
            "",
        ]
    return ["## Strategist brief", "", str(row["brief"]).strip(), ""]


def _section_library_inventory(conn: sqlite3.Connection,
                               problem: str) -> list[str]:
    """All proved goals in this problem (Forward's local toolkit).
    Cross-problem Library promotion is out of Phase 2 scope; just
    same-problem proved lemmas for now."""
    rows = list(conn.execute(
        "SELECT slug, statement FROM goals"
        " WHERE problem = ? AND status = 'proved'"
        " ORDER BY id",
        (problem,),
    ))
    if not rows:
        return ["## Library (proved lemmas in this problem)", "",
                "(none yet)", ""]
    out = ["## Library (proved lemmas in this problem)", ""]
    for r in rows:
        st = str(r["statement"])
        if len(st) > 200:
            st = st[:200].rstrip() + "…"
        out.append(f"- `{r['slug']}`: `{st}`")
    out.append("")
    return out


def _section_forward_history(conn: sqlite3.Connection,
                             problem: str, k: int = 5) -> list[str]:
    """Previous Forward lemmas in this problem (goals.origin='forward')
    so the agent doesn't repropose the same shape."""
    rows = list(conn.execute(
        "SELECT slug, statement, status FROM goals"
        " WHERE problem = ? AND origin = 'forward'"
        " ORDER BY id DESC LIMIT ?",
        (problem, k),
    ))
    if not rows:
        return []
    out = ["## Past Forward proposals (newest first)", ""]
    for r in rows:
        st = str(r["statement"])
        if len(st) > 200:
            st = st[:200].rstrip() + "…"
        out.append(f"- `{r['slug']}` ({r['status']}): `{st}`")
    out.append("")
    return out


def compile_forward_context(conn: sqlite3.Connection, *,
                            problem: str, decision_id: int | None,
                            attempts_dir: Path,
                            workspace: Path,
                            mfst: manifest.Manifest,
                            ) -> Path:
    """Write Context.md for the Forward agent into attempts_dir.

    Sections:
      - Strategist brief (load-bearing input)
      - Library inventory
      - Past Forward proposals
      - TREE.md inline (problem structure)
      - Manifest hints (Mathlib pointers — agent uses loogle Bash for
        type-pattern search)
    """
    sections: list[list[str]] = [
        _section_forward_brief(conn, decision_id),
        _section_library_inventory(conn, problem),
        _section_forward_history(conn, problem),
        _section_tree_inline(workspace, problem),
        _section_manifest_meta(mfst, workspace, problem),
    ]
    parts: list[str] = [f"# Forward context — {problem}", ""]
    for sect in sections:
        parts.extend(sect)
    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    return out
