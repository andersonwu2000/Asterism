"""Statement-level dedup for goals proposed by Backward.

Recognizes when a candidate sub-goal's conclusion is definitionally
equivalent (via Lean kernel `Lean.Meta.isDefEq`) to an ancestor goal's
conclusion. Writes an alias lean file that delegates the proof to the
canonical theorem via Lean tactics, so the candidate inherits
canonical's eventual proof for free.

**Equivalence engine: Lean kernel via `lake env lean`**

`_batch_isdefeq` generates a temp `.lean` file with one
`example : (∀ <a>, ...) = (∀ <b>, ...) := rfl` per pair, runs `lake env
lean`, parses errors back to per-pair pass/fail. Coverage = α + β + η +
definitional unfolding (whatever Lean kernel decides).

Cost: ~3-5s lake-env startup + per-pair elaboration; one batch call
per `find_canonicals_batch`. For Asterism scale (~30 Backwards per
problem × 1 batch each) this is bounded few-minutes overhead.

**Safety rule (strict ancestor)**

Only canonicals that are STRICT ancestors of the candidate's parent
goal are considered (parent_goal_id itself excluded). Justifications:

  1. Lifetime: ancestor's chain is a prefix of candidate's chain, so
     ancestor alive ⇔ candidate alive. Aliasing across OR siblings or
     unrelated branches can break at prune time.

  2. Anti-cycle: aliasing to parent_goal_id is logically circular —
     the candidate is supposed to help prove parent_goal_id, so it
     can't itself be aliased to parent_goal_id's eventual proof. At
     the lake-build level this manifests as an import cycle when
     parent's Verify rewrites parent.lean_path to import the strategy
     scratch which transitively imports the alias which imports
     parent.lean_path.

**Binder count rule (specialization-direction)**

isDefEq alone would reject candidates with strictly more binders than
canonical, even though `apply canonical <;> assumption` could still
discharge them. We apply binder count as a quick pre-filter
(`candidate.binder_count >= canonical.binder_count`) and run isDefEq
on conclusions wrapped in candidate's full ∀-context, so the engine
can match modulo extra hypotheses.

**Alias body**

```lean
theorem candidate_slug <original binders> : <conclusion> := by
  apply canonical_slug <;> assumption
```
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path


_THM_HEAD_RE = re.compile(r"\btheorem\s+\S+")
_SORRY_BODY_RE = re.compile(r":=\s*by\s+sorry")
_LAKE_ERR_RE = re.compile(r"^[^:]+:(\d+):\d+:\s*error", re.MULTILINE)
_BATCH_TIMEOUT_SEC = 240


def _signature_binder_count(text: str) -> int:
    """Count top-level binder groups before the type colon.

    `theorem foo (x : Nat) {α} [Inhabited α] : T := ...` → 3.
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
        return count
    return count


def _extract_full_signature(text: str) -> str | None:
    """Return `<binders> : <conclusion>` portion of the first theorem.

    Given `theorem foo (M : T) (h : U) : Sat M := proof`, returns
    `(M : T) (h : U) : Sat M`. The result is suitable for converting
    into `∀`-form via `_to_forall_form`.
    """
    m = _THM_HEAD_RE.search(text)
    if not m:
        return None
    pos = m.end()
    n = len(text)
    start = pos
    dp = db_ = dk = 0
    while pos < n - 1:
        c = text[pos]
        if c == "(": dp += 1
        elif c == ")": dp -= 1
        elif c == "{": db_ += 1
        elif c == "}": db_ -= 1
        elif c == "[": dk += 1
        elif c == "]": dk -= 1
        elif c == ":" and text[pos + 1] == "=" and dp == 0 and db_ == 0 and dk == 0:
            return text[start:pos].strip()
        pos += 1
    return None


def _to_forall_form(signature: str) -> str:
    """Convert `<binders> : <conclusion>` to `∀ <binders>, <conclusion>`.

    The boundary is the LAST top-level `:` (depth 0 on parens/braces/
    brackets). Empty binders are handled by returning the conclusion
    alone.
    """
    n = len(signature)
    pos = 0
    dp = db_ = dk = 0
    boundary = -1
    while pos < n:
        c = signature[pos]
        if c == "(": dp += 1
        elif c == ")": dp -= 1
        elif c == "{": db_ += 1
        elif c == "}": db_ -= 1
        elif c == "[": dk += 1
        elif c == "]": dk -= 1
        elif c == ":" and dp == 0 and db_ == 0 and dk == 0:
            boundary = pos
        pos += 1
    if boundary < 0:
        return signature
    binders = signature[:boundary].strip()
    conclusion = signature[boundary + 1:].strip()
    if not binders:
        return conclusion
    return f"∀ {binders}, {conclusion}"


def _batch_isdefeq(workspace: Path, problem: str,
                   pairs: list[tuple[str, str]]) -> list[bool]:
    """Run Lean kernel isDefEq on each (a_signature, b_signature) pair.

    `a_signature` and `b_signature` are `<binders> : <conclusion>`
    strings (output of `_extract_full_signature`). Each pair is checked
    by elaborating an `example : <∀-form-a> = <∀-form-b> := rfl`. If
    elaboration succeeds, kernel deemed them def-equivalent.

    Returns a list of bool aligned with `pairs`. On subprocess timeout
    or any error, returns all False (fail-open: never block run_backward).
    """
    if not pairs:
        return []

    lines: list[str] = ["import Mathlib"]
    defs_path = workspace / "Problems" / problem / "Defs.lean"
    if defs_path.exists():
        lines.append(f"import Problems.{problem}.Defs")
    lines.append("")
    lines.append(f"namespace dedupe_check")
    lines.append("")

    pair_start_lines: list[int] = []
    for i, (a_sig, b_sig) in enumerate(pairs):
        a_forall = _to_forall_form(a_sig)
        b_forall = _to_forall_form(b_sig)
        # 1-indexed line of the `example` statement we're about to write
        pair_start_lines.append(len(lines) + 1)
        lines.append(f"-- pair {i}")
        lines.append(f"example : ({a_forall}) = ({b_forall}) := rfl")
        lines.append("")

    lines.append("end dedupe_check")
    content = "\n".join(lines)

    tmp_dir = workspace / ".attempts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_dir / f"_dedupe_check_{uuid.uuid4().hex}.lean"
    tmp_file.write_text(content, encoding="utf-8")

    try:
        r = subprocess.run(
            ["lake", "env", "lean", str(tmp_file)],
            cwd=str(workspace),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=_BATCH_TIMEOUT_SEC,
        )
        output = r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return [False] * len(pairs)
    except OSError:
        return [False] * len(pairs)
    finally:
        try:
            tmp_file.unlink()
        except OSError:
            pass

    error_lines: set[int] = set()
    for m in _LAKE_ERR_RE.finditer(output):
        error_lines.add(int(m.group(1)))

    results: list[bool] = []
    for i, start in enumerate(pair_start_lines):
        end = (pair_start_lines[i + 1] - 1
               if i + 1 < len(pair_start_lines) else len(lines))
        has_error = any(start <= el <= end for el in error_lines)
        results.append(not has_error)
    return results


def _eligible_ancestors(conn: sqlite3.Connection, workspace: Path, *,
                        problem: str, parent_goal_id: int,
                        candidate_count: int) -> list[sqlite3.Row]:
    """Strict ancestors of `parent_goal_id` whose binder count ≤
    `candidate_count`. Filtered to alive lineage and status in
    proved/open/attempting. Sorted by status='proved' DESC, id ASC."""
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
        "  SELECT s.goal_id FROM strategies s"
        "    JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        "    WHERE ss.subgoal_id = ?"
        "  UNION"
        "  SELECT s.goal_id FROM strategies s"
        "    JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        "    JOIN ancestors a ON a.id = ss.subgoal_id"
        ") "
        "SELECT g.id, g.statement, g.lean_path, g.status FROM goals g "
        "WHERE g.id IN alive AND g.id IN ancestors "
        "  AND g.problem = ? "
        "  AND g.status IN ('proved','open','attempting') "
        "ORDER BY (g.status = 'proved') DESC, g.id ASC",
        (problem, parent_goal_id, problem),
    ).fetchall()

    eligible = []
    for r in rows:
        try:
            canon_text = (workspace / r["lean_path"]).read_text(
                encoding="utf-8")
        except OSError:
            continue
        if _signature_binder_count(canon_text) > candidate_count:
            continue
        eligible.append((r, canon_text))
    return eligible


def find_canonicals_batch(
    conn: sqlite3.Connection, workspace: Path, *,
    problem: str, parent_goal_id: int,
    candidates: list[tuple[str, str]],
) -> list[int | None]:
    """Batch dedupe lookup: for each candidate, return canonical
    goal_id (or None).

    `candidates`: list of (slug, full_text) for each sub-goal proposed
    by the current Backward. Returns a list aligned with `candidates`.

    All eligible (candidate, canonical) pairs are bundled into a single
    `_batch_isdefeq` subprocess call to amortize lake env startup
    cost. Per-candidate canonical selection follows DB priority
    (proved > open > attempting; earliest id tie-break).
    """
    n = len(candidates)
    if n == 0:
        return []

    # Per-candidate eligible-ancestor list (already binder-count filtered)
    cand_ancestors: list[list[tuple[sqlite3.Row, str]]] = []
    for slug, full_text in candidates:
        sig = _extract_full_signature(full_text)
        if sig is None or not sig.strip():
            cand_ancestors.append([])
            continue
        cand_count = _signature_binder_count(full_text)
        cand_ancestors.append(_eligible_ancestors(
            conn, workspace, problem=problem,
            parent_goal_id=parent_goal_id, candidate_count=cand_count,
        ))

    # Build flat list of pairs to check; track origin (cand_idx, anc_row)
    pairs: list[tuple[str, str]] = []
    pair_origin: list[tuple[int, sqlite3.Row]] = []
    for ci, (slug, full_text) in enumerate(candidates):
        cand_sig = _extract_full_signature(full_text)
        if cand_sig is None:
            continue
        for anc_row, anc_text in cand_ancestors[ci]:
            anc_sig = _extract_full_signature(anc_text)
            if anc_sig is None:
                continue
            pairs.append((cand_sig, anc_sig))
            pair_origin.append((ci, anc_row))

    if not pairs:
        return [None] * n

    flags = _batch_isdefeq(workspace, problem, pairs)

    # First-hit per candidate (pair_origin is already in DB priority order
    # because cand_ancestors[ci] was sorted by query)
    canonical_for: list[int | None] = [None] * n
    for (ci, anc_row), is_eq in zip(pair_origin, flags):
        if not is_eq:
            continue
        if canonical_for[ci] is not None:
            continue  # already picked higher-priority canonical
        canonical_for[ci] = int(anc_row["id"])
    return canonical_for


def build_alias_content(*, original_content: str,
                        canonical_module: str,
                        canonical_slug: str) -> str:
    """Take the candidate's original sub-goal lean text and produce its
    alias version: inject `import canonical_module` and rewrite the
    sorry-stub body to delegate to canonical via tactics.
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
