"""Statement-level dedup for goals proposed by Backward.

Recognizes when a candidate sub-goal is provable from an existing
goal (ancestor / orphan sibling / cross-branch proved). Writes an
alias lean file that delegates the proof to the canonical theorem via
`apply canonical <;> assumption`, so the candidate inherits
canonical's eventual proof for free.

**Provability engine: Lean kernel via `lake env lean`**

`_batch_provable_via_apply` generates a temp `.lean` file with one
`theorem _dc_i <cand binders> : <cand conclusion> := by apply
@<canonical> <;> assumption` per pair, runs `lake env lean`, parses
errors back to per-pair pass/fail. The check semantics matches what
`build_alias_content` actually writes for the alias body, so anything
the check accepts can be safely aliased.

Note: this replaced an earlier `_batch_isdefeq` rfl-based check
(2026-05-11). The rfl check rejected hypothesis-extension cases
(SG run #15: Goals 323 vs 329 were the same conclusion with extra
redundant hypotheses; rfl said "different types"; alias would have
worked because `apply <;> assumption` discharges extras). The
provability check matches alias semantics exactly.

Cost: ~3-5s lake-env startup + per-pair elaboration; one batch call
per `find_canonicals_batch`. For Asterism scale (~30 Backwards per
problem × 1 batch each) this is bounded few-minutes overhead.

**Safety rules**

Two canonical sources, both with their own justification:

(1) STRICT ANCESTORS of candidate's parent goal. Excludes
    parent_goal_id itself:

    a. Lifetime: ancestor's chain is a prefix of candidate's chain,
       so ancestor alive ⇔ candidate alive.
    b. Anti-cycle: aliasing to parent_goal_id is logically circular —
       the candidate is supposed to help prove parent_goal_id, so it
       can't itself be aliased to parent_goal_id's eventual proof. At
       the lake-build level this manifests as an import cycle when
       parent's Verify rewrites parent.lean_path to import the strategy
       scratch which transitively imports the alias which imports
       parent.lean_path.

(2) **Orphan proved sub-goals** of dead/superseded strategies on the
    same parent goal (cross-strategy reuse). Justifications:

    a. Lifetime: orphan's lean file already exists on disk (it was
       proved before its strategy died). prune retains it as long as
       any live goal aliases to it (see goals.alias_target_id +
       prune.is_retained).
    b. Anti-cycle: orphan was a sub-goal of a sibling strategy on the
       same parent, not on candidate's chain — no import loop.

    Without this rule, a parent that loses one sub-goal to shelve
    re-Backwards from scratch and re-proves all the salvageable
    siblings — observed waste on compactness 2026-05-02 was ~20
    sub-goals.

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
from typing import NamedTuple

from ..state import db


# Signature extractor: matches declarations that always carry an
# explicit type signature, i.e. `theorem` / `lemma` (lemma is just an
# alias for theorem in Lean 4). NOT extended to `def` — definitional
# entries may be of the form `def foo := value` with no signature, and
# `_extract_full_signature` walks the text expecting `<binders> : ...
# := ...` shape. The name extractor below is what needs to see `def`.
_THM_HEAD_RE = re.compile(r"\b(?:theorem|lemma)\s+\S+")
_SORRY_BODY_RE = re.compile(r":=\s*by\s+sorry")
# Lake/Lean error line: `<path>:<line>:<col>: error: ...`.
# Old regex used `[^:]+` for the path part, which breaks on Windows
# absolute paths starting with a drive letter (`D:\Asterism\...`) —
# `[^:]+` stops at the drive-letter colon, the rest of the path is
# not all-digits, so the entire regex misses. With no error lines
# matched, `_batch_provable_via_apply` would then hit its "no
# error_lines despite rc!=0" branch and return all-False, defeating
# per-pair attribution. Using lazy `.+?` lets the path contain any
# number of colons; the `\d+:\d+` line-col anchor at the right tail
# unambiguously identifies the boundary.
_LAKE_ERR_RE = re.compile(r"^.+?:(\d+):\d+:\s*error", re.MULTILINE)
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


# Match `theorem`, `lemma`, or `def` to cover framework-promoted ancestors
# (see _THM_HEAD_RE for the case background).
_THM_NAME_RE = re.compile(r"\b(?:theorem|lemma|def)\s+(\S+)")


def _extract_theorem_name(text: str) -> str | None:
    """Extract the declared name from the first `theorem|lemma|def
    <name>` in the file. Returns None if none found."""
    m = _THM_NAME_RE.search(text)
    return m.group(1) if m else None


def _batch_provable_via_apply(
    workspace: Path,
    problem: str,
    pairs: list[tuple[str, str, str]],
) -> list[bool]:
    """For each (cand_signature, canonical_module, canonical_thm_name)
    pair, check if `apply @canonical <;> assumption` proves
    `<cand_signature>`.

    `cand_signature` is `<binders> : <conclusion>` (output of
    `_extract_full_signature`).
    `canonical_module` is the Lean module to import for canonical.
    `canonical_thm_name` is the theorem name inside that module.

    Replaces the prior `_batch_isdefeq` (2026-05-11). The rfl check
    rejected hypothesis-extension cases (Goals 323 vs 329 in SG run
    #15 — same conclusion with extra hypotheses). The provability
    check via `apply <;> assumption` matches `build_alias_content`'s
    alias body semantics: anything this accepts can be aliased
    successfully.

    Returns a list of bool aligned with `pairs`. On subprocess
    timeout or any error, returns all False (fail-open: never block
    run_backward).
    """
    if not pairs:
        return []

    lines: list[str] = ["import Mathlib"]
    defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
    if defs_path.exists():
        lines.append(f"import Problems.{problem}.Defs")

    seen_modules: set[str] = set()
    for _, mod, _ in pairs:
        if mod and mod not in seen_modules:
            lines.append(f"import {mod}")
            seen_modules.add(mod)

    lines.append("")
    lines.append("namespace dedupe_check")
    lines.append("")

    pair_start_lines: list[int] = []
    for i, (cand_sig, canonical_module, canonical_thm) in enumerate(pairs):
        # canonical_thm should already be the bare theorem name (e.g.
        # "kelly_min_exists"). The canonical_module's namespace
        # convention for sub-goals is `Problems.<problem>` (matches
        # files in Problems/<problem>/proofs/). We invoke via the FQN
        # to disambiguate when an ancestor and a sibling share a name.
        if not canonical_thm:
            # No theorem name extracted — pair is unusable; emit a
            # syntactically-broken stub so its line attributes the error
            # to this pair only (not a global error swallowing siblings).
            pair_start_lines.append(len(lines) + 1)
            lines.append(f"-- pair {i} (no canonical theorem name)")
            lines.append(f"theorem _dc_{i} : True := by trivial_unknown_tac_force_fail")
            lines.append("")
            continue
        canonical_fqn = f"Problems.{problem}.{canonical_thm}"
        # Flatten cand_sig whitespace: candidate signatures extracted
        # from on-disk theorems often span multiple lines (long ∀-prefixed
        # statements wrap for readability). Embedding a multi-line cand_sig
        # via `lines.append(<one-string>)` makes the file's line count
        # diverge from `len(lines)`, throwing off pair_start_lines and
        # causing lake errors to land outside the (Python-tracked) pair
        # range → global-error short-circuit → all pairs False. Collapse
        # all whitespace runs to single spaces so the appended string
        # remains one file line.
        cand_sig_flat = " ".join(cand_sig.split())
        pair_start_lines.append(len(lines) + 1)
        lines.append(f"-- pair {i}")
        lines.append(f"theorem _dc_{i} {cand_sig_flat} := by")
        lines.append(f"  apply @{canonical_fqn} <;> assumption")
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
        rc = r.returncode
    except subprocess.TimeoutExpired:
        return [False] * len(pairs)
    except OSError:
        return [False] * len(pairs)
    finally:
        try:
            tmp_file.unlink()
        except OSError:
            pass

    # Fast path: if Lean is happy with the entire file, every pair passed.
    if rc == 0:
        return [True] * len(pairs)

    # rc != 0 means at least one error. Walk error lines and partition
    # them by which pair's range they fall into. Errors outside any
    # pair range are GLOBAL (e.g. import not found, namespace mis-parse,
    # earlier example bailing the elaborator). A global error invalidates
    # the run — Lean may have stopped before reaching later pairs, so
    # absence-of-error in their line range does NOT mean isDefEq passed.
    # Conservative: treat all pairs as False on global error.
    error_lines: set[int] = set()
    for m in _LAKE_ERR_RE.finditer(output):
        error_lines.add(int(m.group(1)))

    in_any_pair = set()
    for el in error_lines:
        for i, start in enumerate(pair_start_lines):
            end = (pair_start_lines[i + 1] - 1
                   if i + 1 < len(pair_start_lines) else len(lines))
            if start <= el <= end:
                in_any_pair.add(el)
                break

    if error_lines - in_any_pair:
        # Global error present: rc said failure but the failure is not
        # attributable to a single pair. Refuse all.
        return [False] * len(pairs)

    if not error_lines:
        # rc != 0 but regex matched no line-prefixed errors. Conservative:
        # the failure pattern is unfamiliar; refuse all rather than
        # silently accept.
        return [False] * len(pairs)

    # Per-pair attribution: pair fails iff at least one error line falls
    # in its range.
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


def _eligible_orphan_subgoals(conn: sqlite3.Connection, workspace: Path, *,
                              problem: str, parent_goal_id: int,
                              candidate_count: int,
                              ) -> list[tuple[sqlite3.Row, str]]:
    """Proved sub-goals from dead/superseded strategies on the
    same parent goal. They're orphaned by the alive-chain walk, but
    their lean files still hold valid proofs we can alias against.
    Filters by binder count (same as ancestors) and by file readability.

    Excludes goals already inserted as aliases (alias_target_id IS NOT
    NULL) — chasing alias chains complicates lifetime reasoning. The
    pool is "real proofs only".
    """
    rows = conn.execute(
        "SELECT g.id, g.statement, g.lean_path, g.status FROM goals g "
        "JOIN strategy_subgoals ss ON ss.subgoal_id = g.id "
        "JOIN strategies s ON s.id = ss.strategy_id "
        "WHERE s.goal_id = ? "
        "  AND s.status IN ('dead', 'superseded') "
        "  AND g.problem = ? "
        "  AND g.status = 'proved' "
        "  AND g.alias_target_id IS NULL "
        "ORDER BY g.id ASC",
        (parent_goal_id, problem),
    ).fetchall()

    eligible: list[tuple[sqlite3.Row, str]] = []
    seen: set[int] = set()
    for r in rows:
        if r["id"] in seen:
            continue  # a goal can be linked from multiple dead strategies
        seen.add(int(r["id"]))
        try:
            canon_text = (workspace / r["lean_path"]).read_text(
                encoding="utf-8")
        except OSError:
            continue
        if _signature_binder_count(canon_text) > candidate_count:
            continue
        eligible.append((r, canon_text))
    return eligible


def _eligible_problem_proved(conn: sqlite3.Connection, workspace: Path, *,
                             problem: str, parent_goal_id: int,
                             candidate_count: int,
                             exclude_ids: set[int],
                             ) -> list[tuple[sqlite3.Row, str]]:
    """Proved goals anywhere in the same Problem (cross-branch). Catches
    the case where two independent decomposition branches landed on
    type-equivalent sub-goals — the strict-ancestor / orphan-sibling
    pools don't see this.

    Excludes:
    - `parent_goal_id` (aliasing to your own parent is a logical cycle).
    - `alias_target_id IS NOT NULL` (no alias chains; pool stays "real
      proofs only", same rule as `_eligible_orphan_subgoals`).
    - `exclude_ids` (caller passes ancestors + orphans already counted
      so we don't double-emit pairs into the batch).

    Anti-cycle: a proved goal G's `lean_path` is concrete on disk —
    elaborated against its own already-proved sub-tree, with no
    placeholder slots. Importing G from candidate's alias file is
    therefore non-recursive at lake-build time. (Contrast the ancestor
    case where parent is transitively waiting for candidate's proof,
    so aliasing candidate to parent would loop.)
    """
    # Guard against `NOT IN ()` / `NOT IN (NULL)` — both filter all rows
    # out in SQLite. When `exclude_ids` is empty (root-adjacent Backward
    # with no ancestors yet — exactly when cross-branch dedup is most
    # useful), drop the clause entirely.
    if exclude_ids:
        placeholders = ",".join("?" for _ in exclude_ids)
        exclude_clause = f" AND g.id NOT IN ({placeholders})"
        params = (problem, parent_goal_id, *exclude_ids)
    else:
        exclude_clause = ""
        params = (problem, parent_goal_id)
    rows = conn.execute(
        f"SELECT g.id, g.statement, g.lean_path, g.status FROM goals g "
        f"WHERE g.problem = ? AND g.status = 'proved' "
        f"  AND g.alias_target_id IS NULL "
        f"  AND g.id != ?"
        f"{exclude_clause} "
        f"ORDER BY g.id ASC",
        params,
    ).fetchall()

    eligible: list[tuple[sqlite3.Row, str]] = []
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


def _eligible_disproved(conn: sqlite3.Connection, workspace: Path, *,
                        problem: str, parent_goal_id: int,
                        candidate_count: int,
                        ) -> list[tuple[sqlite3.Row, str]]:
    """Disproved goals in same Problem whose lean files are still on
    disk (prune kept them, or they were never pruned). Used to detect
    that a candidate sub-goal recapitulates a statement we've already
    confirmed false (agent gave a counterexample, status='disproved').
    Different semantics from the alive/proved pools: a disproved hit
    means "decline this candidate", not "alias to canonical".

    Phase 2 — previously this looked at `status='shelved'`. The status
    enum split (see `docs/phase2/pipelines.md` §4.1) moved soft-terminal
    goals (parent_needs_fix / ConfirmShelve cascade) to a separate
    'shelved' that dedupe does NOT block. Only 'disproved' (agent
    counterexample) blocks future proposals.

    Excludes parent_goal_id (own-parent loop guard, same as other pools)
    and alias rows (no alias chain). Binder count pre-filter same as
    `_eligible_ancestors`.

    The file existence check is best-effort: if the disproved goal's
    lean file was pruned but the DB row survives, the pair simply can't
    be elaborated by `_batch_provable_via_apply`. That's fine — the row
    won't contribute to the batch and the candidate falls through to
    the alive/proved comparison.
    """
    rows = conn.execute(
        "SELECT g.id, g.statement, g.lean_path, g.status FROM goals g "
        "WHERE g.problem = ? AND g.status = 'disproved' "
        "  AND g.alias_target_id IS NULL "
        "  AND g.id != ? "
        "ORDER BY g.id ASC",
        (problem, parent_goal_id),
    ).fetchall()

    eligible: list[tuple[sqlite3.Row, str]] = []
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


class CanonicalMatch(NamedTuple):
    """Result of a dedupe hit on one candidate.

    `kind`:
      - `"alias"`: canonical is alive/proved — caller should write an
        alias body and insert the candidate as `proved` aliased to
        `goal_id`.
      - `"disproved"`: canonical is disproved (agent showed a
        counterexample) — caller should decline this candidate. The
        proposed statement is already known false. `goal_id` is the
        disproved goal so the caller can surface its dead_attempt
        forensic in the decline message.
    """
    goal_id: int
    kind: str  # Literal["alias", "disproved"]


def find_canonicals_batch(
    conn: sqlite3.Connection, workspace: Path, *,
    problem: str, parent_goal_id: int,
    candidates: list[tuple[str, str]],
) -> list[CanonicalMatch | None]:
    """Batch dedupe lookup: for each candidate, return a CanonicalMatch
    (alias or disproved) or None.

    `candidates`: list of (slug, full_text) for each sub-goal proposed
    by the current Backward. Returns a list aligned with `candidates`.

    All eligible (candidate, canonical) pairs are bundled into a single
    `_batch_provable_via_apply` subprocess call to amortize lake env
    startup cost. Per-candidate canonical selection follows priority:
      1. Strict ancestors (alive lineage; proved > open > attempting)
      2. Orphan proved siblings of dead/superseded strategies
      3. Cross-branch proved goals in same problem
      4. Disproved goals in same problem → kind="disproved" (decline)
    Tiers 1-3 yield `kind="alias"`. Tier 4 yields `kind="disproved"`.

    Phase 2 — Tier 4 looks at `status='disproved'` (was `'shelved'`).
    Soft-terminal 'shelved' goals (parent_needs_fix / ConfirmShelve
    cascade) no longer block future proposals.
    """
    n = len(candidates)
    if n == 0:
        return []

    # Per-candidate eligible canonicals. Alive/proved tiers come first
    # so they take precedence on first-hit. The disproved tier is appended
    # afterwards and only contributes when no alive/proved canonical
    # exists for the candidate. Tag each row with its source kind so
    # the assembly loop below can emit the right `CanonicalMatch.kind`.
    KIND_ALIAS = "alias"
    KIND_DISPROVED = "disproved"
    cand_pools: list[list[tuple[sqlite3.Row, str, str]]] = []
    for slug, full_text in candidates:
        sig = _extract_full_signature(full_text)
        if sig is None or not sig.strip():
            cand_pools.append([])
            continue
        cand_count = _signature_binder_count(full_text)
        anc = _eligible_ancestors(
            conn, workspace, problem=problem,
            parent_goal_id=parent_goal_id, candidate_count=cand_count,
        )
        orph = _eligible_orphan_subgoals(
            conn, workspace, problem=problem,
            parent_goal_id=parent_goal_id, candidate_count=cand_count,
        )
        seen_ids = {int(r["id"]) for r, _ in anc} | {int(r["id"]) for r, _ in orph}
        cross = _eligible_problem_proved(
            conn, workspace, problem=problem,
            parent_goal_id=parent_goal_id, candidate_count=cand_count,
            exclude_ids=seen_ids,
        )
        disproved = _eligible_disproved(
            conn, workspace, problem=problem,
            parent_goal_id=parent_goal_id, candidate_count=cand_count,
        )
        pool: list[tuple[sqlite3.Row, str, str]] = []
        for r, t in anc + orph + cross:
            pool.append((r, t, KIND_ALIAS))
        for r, t in disproved:
            pool.append((r, t, KIND_DISPROVED))
        cand_pools.append(pool)

    # Build flat list of pairs to check; track origin (cand_idx, row, kind).
    # Each pair: (cand_signature, canonical_module, canonical_theorem_name).
    # Canonical's module is derived from anc_row's lean_path; theorem
    # name extracted from anc_text directly (DB slug ≠ on-disk theorem
    # name in some framework-promoted / aliased cases, where the file
    # body is `def <slug> := @s<sid>` — see _THM_HEAD_RE comment).
    pairs: list[tuple[str, str, str]] = []
    pair_origin: list[tuple[int, sqlite3.Row, str]] = []
    for ci, (slug, full_text) in enumerate(candidates):
        cand_sig = _extract_full_signature(full_text)
        if cand_sig is None:
            continue
        for anc_row, anc_text, kind in cand_pools[ci]:
            canonical_thm = _extract_theorem_name(anc_text) or ""
            # DB stores workspace-relative lean_path strings; resolve
            # to absolute before module conversion.
            anc_lean_path = workspace / anc_row["lean_path"]
            from ..pipeline._lake import lean_path_to_module
            try:
                canonical_module = lean_path_to_module(workspace, anc_lean_path)
            except (ValueError, OSError):
                continue
            pairs.append((cand_sig, canonical_module, canonical_thm))
            pair_origin.append((ci, anc_row, kind))

    if not pairs:
        return [None] * n

    flags = _batch_provable_via_apply(workspace, problem, pairs)

    # First-hit per candidate. pair_origin order is alive→disproved within
    # each candidate (because cand_pools concatenates alive first), so
    # the first True flag picked up is automatically the highest-priority
    # match. An "alias" hit therefore shadows a later "disproved" hit on
    # the same candidate — the desired behavior (an alive canonical is
    # always more useful than a disproved precedent).
    result: list[CanonicalMatch | None] = [None] * n
    for (ci, anc_row, kind), is_eq in zip(pair_origin, flags):
        if not is_eq:
            continue
        if result[ci] is not None:
            continue
        result[ci] = CanonicalMatch(goal_id=int(anc_row["id"]), kind=kind)
    # Lightweight metric — surfaces dedupe effectiveness in the daemon
    # log so Phase 2 design (Strategist/Forward/Librarian) has empirical
    # input on alias hit rate and disproved-collision frequency. Pre-fix
    # the entire Windows-side dedupe pipeline was silently producing
    # zeros here; this print is how we'll catch any future regression.
    n_alias = sum(1 for m in result if m and m.kind == "alias")
    n_disproved = sum(1 for m in result if m and m.kind == "disproved")
    print(f"[dedupe] checked {n} candidate(s) against {len(pairs)} "
          f"pair(s); alias={n_alias} disproved={n_disproved}", flush=True)
    return result


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
