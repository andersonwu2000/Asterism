"""Statement-level dedup for goals proposed by Backward.

Recognizes when a candidate sub-goal's conclusion already appears in an
ancestor goal of the same problem. Writes an alias lean file that
delegates the proof to the canonical theorem via Lean tactics, so the
candidate inherits canonical's eventual proof for free.

**Safety rule (ancestor-only)**

Only canonicals that are ancestors of the candidate's parent goal are
considered. Justification: a goal is alive iff every strategy on its
chain back to a root is alive. An ancestor's chain is a prefix of the
candidate's chain, so ancestor alive ⇔ candidate alive. Aliasing within
an ancestor never breaks at prune time. Cross-strategy / OR-sibling
canonicals are excluded because they can die independently.

**Binder count rule (specialization-direction)**

Conclusion match alone is unsafe: a candidate with strictly more
hypotheses (`(M) (hM) (hMax) (hComp) (hCons) (hConj) : Sat M`) has the
same conclusion as a generalization (`(M) (hM) (hMax) : Sat M`), but
not vice versa. We require `candidate.binder_count >= canonical.binder_count`
so that aliasing is "canonical generalizes candidate" — the unused
hypotheses in candidate are silently discarded by Lean.

**Alias body**

```lean
theorem candidate_slug <original binders> : <conclusion> := by
  apply canonical_slug <;> assumption
```

`apply` unifies conclusions; `<;> assumption` discharges any new
metavariables by typed-hypothesis lookup against candidate's binder
list. No need to parse binder names — Lean handles it.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path


_THM_HEAD_RE = re.compile(r"\btheorem\s+\S+")
_SORRY_BODY_RE = re.compile(r":=\s*by\s+sorry")
_WS_RE = re.compile(r"\s+")


def _normalize_statement(s: str) -> str:
    """Collapse all whitespace to single spaces; strip ends."""
    return _WS_RE.sub(" ", s.strip())


def _signature_binder_count(text: str) -> int:
    """Count top-level binder groups before the type colon.

    `theorem foo (x : Nat) {α} [Inhabited α] : T := ...` → 3.
    Used to enforce that an alias's candidate has at least as many
    binders as the canonical it aliases to (specialization direction).
    """
    m = _THM_HEAD_RE.search(text)
    if not m:
        return 0
    pos = m.end()
    n = len(text)
    count = 0
    while pos < n:
        while pos < n and text[pos].isspace():
            pos += 1
        if pos >= n:
            return count
        ch = text[pos]
        if ch in "({[":
            count += 1
            close = {"(": ")", "{": "}", "[": "]"}[ch]
            depth = 1
            pos += 1
            while pos < n and depth > 0:
                if text[pos] == ch:
                    depth += 1
                elif text[pos] == close:
                    depth -= 1
                pos += 1
            continue
        if ch == ":":
            return count
        # Unexpected token (e.g. malformed input) — bail out
        return count
    return count


def find_canonical(conn: sqlite3.Connection, workspace: Path, *,
                   problem: str, parent_goal_id: int,
                   candidate_full_text: str,
                   candidate_conclusion: str) -> int | None:
    """Return goal_id of an ancestor goal whose conclusion matches and
    whose binder count ≤ candidate's. None if no safe canonical found.

    `parent_goal_id`: the goal currently being decomposed (the new
    strategy's parent). Used as the start of the ancestor walk.
    """
    if not candidate_conclusion.strip():
        return None
    candidate_norm = _normalize_statement(candidate_conclusion)
    candidate_count = _signature_binder_count(candidate_full_text)

    rows = conn.execute(
        "WITH RECURSIVE alive(id) AS ("
        "  SELECT id FROM goals WHERE problem = ? AND origin = 'root'"
        "  UNION"
        "  SELECT g.id FROM goals g"
        "  JOIN strategy_subgoals ss ON ss.subgoal_id = g.id"
        "  JOIN strategies s ON s.id = ss.strategy_id"
        "  JOIN alive a ON a.id = s.goal_id"
        "  WHERE s.status IN ('proposed','succeeded')"
        "), ancestors(id) AS ("
        "  SELECT ?"
        "  UNION"
        "  SELECT s.goal_id FROM strategies s"
        "  JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        "  JOIN ancestors a ON a.id = ss.subgoal_id"
        ") "
        "SELECT g.id, g.statement, g.lean_path, g.status FROM goals g "
        "WHERE g.id IN alive AND g.id IN ancestors "
        "  AND g.problem = ? "
        "  AND g.status IN ('proved','open','attempting') "
        "ORDER BY (g.status = 'proved') DESC, g.id ASC",
        (problem, parent_goal_id, problem),
    ).fetchall()

    for r in rows:
        if _normalize_statement(r["statement"]) != candidate_norm:
            continue
        # Binder count check requires reading canonical's lean file
        # (DB only stores the conclusion, not the full signature).
        try:
            canon_text = (workspace / r["lean_path"]).read_text(
                encoding="utf-8")
        except OSError:
            continue
        canon_count = _signature_binder_count(canon_text)
        if candidate_count < canon_count:
            continue
        return int(r["id"])
    return None


def build_alias_content(*, original_content: str,
                        canonical_module: str,
                        canonical_slug: str) -> str:
    """Take the candidate's original sub-goal lean text and produce its
    alias version: inject `import canonical_module` and rewrite the
    sorry-stub body to delegate to canonical via tactics.

    The original signature (binders + conclusion) is preserved verbatim
    — only the body changes. This means Lean sees the candidate's full
    binder list when elaborating the body, so `apply canonical_slug
    <;> assumption` discharges canonical's hypotheses by type lookup
    against candidate's binders.
    """
    if f"import {canonical_module}" not in original_content:
        lines = original_content.split("\n")
        last_import = -1
        for i, line in enumerate(lines):
            if line.startswith("import "):
                last_import = i
        if last_import >= 0:
            lines.insert(last_import + 1, f"import {canonical_module}")
        else:
            lines.insert(0, f"import {canonical_module}")
        original_content = "\n".join(lines)

    return _SORRY_BODY_RE.sub(
        f":= by apply {canonical_slug} <;> assumption",
        original_content,
        count=1,
    )
