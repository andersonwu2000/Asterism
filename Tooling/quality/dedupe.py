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

Stays COLD (not the warm gateway): task #108 measured a gateway
`verify_file` of this throwaway Mathlib-importing file at ~24s every
call (warmth only helps incremental re-edits of the same slot, not a
fresh file's import environment) — no faster than cold `lake env lean`
(~20s) and it would tie up a gateway worker slot. So the cold subprocess
is kept (one of the few deliberate cold-lake exceptions, data-flow §0).

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

import math
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
# Lake/Lean error line: `<path>:<line>:<col>: error: ...`. Lazy `.+?` for
# the path part so a Windows drive-letter colon (`D:\...`) doesn't abort
# the match; the `\d+:\d+` line-col anchor identifies the boundary.
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


def _type_colon_pos(signature: str) -> int:
    """Index of the type colon in `<binders> : <conclusion>` — the FIRST
    depth-0 `:`. Binder colons (`(x : T)`, `{n : ℕ}`, `[i : I]`, `⦃s : S⦄`)
    are bracketed (depth > 0); a colon in the CONCLUSION itself (`∃ x : E, …`,
    `∀ x : T, …`, `fun y : T => …`) comes AFTER the type colon, so the FIRST
    depth-0 colon is the true split. Returns -1 if none (no binders, e.g. a
    bare conclusion). The old LAST-depth-0-colon scan mangled ∃/∀/fun-bearing
    conclusions — this is the canonical splitter both `_to_forall_form` and
    `_conclusion_of_signature` use; `librarian.dedup.sig_to_forall` shares it."""
    dp = db_ = dk = da = 0
    for i, c in enumerate(signature):
        if c == "(": dp += 1
        elif c == ")": dp -= 1
        elif c == "{": db_ += 1
        elif c == "}": db_ -= 1
        elif c == "[": dk += 1
        elif c == "]": dk -= 1
        elif c == "⦃": da += 1
        elif c == "⦄": da -= 1
        elif c == ":" and dp == db_ == dk == da == 0:
            return i
    return -1


def _to_forall_form(signature: str) -> str:
    """Convert `<binders> : <conclusion>` to `∀ <binders>, <conclusion>`.
    Splits at the type colon (`_type_colon_pos`, the FIRST depth-0 `:`);
    empty binders return the conclusion alone."""
    p = _type_colon_pos(signature)
    if p < 0:
        return signature.strip()
    binders = signature[:p].strip()
    conclusion = signature[p + 1:].strip()
    return f"∀ {binders}, {conclusion}" if binders else conclusion


# Match `theorem`, `lemma`, or `def` to cover framework-promoted ancestors
# (see _THM_HEAD_RE for the case background).
_THM_NAME_RE = re.compile(r"\b(?:theorem|lemma|def)\s+(\S+)")


def _extract_theorem_name(text: str) -> str | None:
    """Extract the declared name from the first `theorem|lemma|def
    <name>` in the file. Returns None if none found."""
    m = _THM_NAME_RE.search(text)
    return m.group(1) if m else None


# ---------------------------------------------------------------------
# Library reuse pool (A — cross-problem dedup)
#
# A freshly-proposed Backward sub-goal that an already-proved `Library/`
# decl can close via `apply @<fqn> <;> assumption` should be aliased to
# that decl (proved immediately) instead of being re-derived. This is the
# in-problem dedup machinery pointed at a cross-problem pool: the
# canonical lives in Library/, not the `goals` table, so it carries
# (module, fqn) rather than a goal row. Domain-scoped; pre-filtered by
# binder count + distinctive-token overlap so the probe never imports the
# whole domain Library (import-closure cost, not pair count, dominates).
# Source of truth = `Library/INDEX.md` (the Librarian done-marker): each
# line is `- `<fqn>` → `<rel path>``; module = fqn minus last segment.
# ---------------------------------------------------------------------

_LIB_INDEX_ENTRY_RE = re.compile(r"^-\s+`([\w.]+)`\s*(?:→|->)\s*`([^`]+)`")
_LIB_DECL_HEAD_RE = re.compile(
    r"(?m)^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
    r"(?:private[ \t]+|protected[ \t]+|noncomputable[ \t]+|scoped[ \t]+)*"
    r"(theorem|lemma|def)[ \t]+([A-Za-z_][\w'.]*)")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")
# Identifiers too common to be distinctive for the overlap pre-filter.
_LIB_STOPWORDS = frozenset({
    "fun", "Type", "Prop", "Sort", "by", "with", "fun", "Eq", "And", "Or",
})


def _conclusion_of_signature(signature: str) -> str:
    """The `<conclusion>` of `<binders> : <conclusion>` — text after the type
    colon (`_type_colon_pos`, the FIRST depth-0 `:`). A `∃ x : T,` / `∀ x : T,`
    / `fun y : T =>` colon in the conclusion is NOT the boundary (the old
    LAST-colon scan returned a mangled tail for those)."""
    p = _type_colon_pos(signature)
    return signature[p + 1:].strip() if p >= 0 else signature.strip()


def _distinctive_tokens(text: str) -> "frozenset[str]":
    """Identifier tokens (len > 1, minus stopwords) in a conclusion — the
    cheap signal for the overlap pre-filter. No Lean parsing, so robust to
    notation / pretty-printing differences."""
    return frozenset(t for t in _IDENT_RE.findall(text)
                     if len(t) > 1 and t not in _LIB_STOPWORDS)


def _parse_library_decl_sigs(text: str) -> "dict[str, tuple[int, str]]":
    """Map each theorem/lemma decl in a (multi-decl) Library file to
    (binder_count, conclusion). `def`s are skipped: `apply @def` rarely
    discharges a goal and `def foo := v` has no signature to extract. Each
    decl's text chunk (header → next header) runs through the SAME tested
    `_extract_full_signature` / `_signature_binder_count` used for
    single-decl sub-goal files."""
    heads = list(_LIB_DECL_HEAD_RE.finditer(text))
    out: dict[str, tuple[int, str]] = {}
    for i, m in enumerate(heads):
        if m.group(1) == "def":
            continue
        name = m.group(2)
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        chunk = text[m.start():end]
        sig = _extract_full_signature(chunk)
        if sig is None or not sig.strip():
            continue
        out[name] = (_signature_binder_count(chunk),
                     _conclusion_of_signature(sig))
    return out


class _LibCanon(NamedTuple):
    fqn: str            # fully-qualified name to `apply @`
    module: str         # Library module to import
    binder_count: int
    concl_tokens: "frozenset[str]"


# Per-process cache keyed by (workspace, domain, INDEX mtime) — Library is
# static during a problem run; mtime in the key invalidates on edit.
_LIBRARY_INDEX_CACHE: "dict[tuple[str, str, float], list[_LibCanon]]" = {}


def _library_canonicals(workspace: Path, domain: str) -> "list[_LibCanon]":
    """All theorem/lemma Library decls in `domain`, with binder count +
    conclusion tokens, parsed from `Library/INDEX.md` + the referenced
    files. Cached per (workspace, domain, INDEX mtime)."""
    index = workspace / "Library" / "INDEX.md"
    try:
        mtime = index.stat().st_mtime
    except OSError:
        return []
    key = (str(workspace), domain, mtime)
    cached = _LIBRARY_INDEX_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        text = index.read_text(encoding="utf-8")
    except OSError:
        return []
    by_file: dict[str, list[str]] = {}
    for ln in text.splitlines():
        m = _LIB_INDEX_ENTRY_RE.match(ln.strip())
        if not m:
            continue
        fqn, rel = m.group(1), m.group(2).strip()
        parts = rel.replace("\\", "/").split("/")
        if len(parts) >= 2 and parts[0] == "Library" and parts[1] == domain:
            by_file.setdefault(rel, []).append(fqn)
    out: list[_LibCanon] = []
    for rel, fqns in by_file.items():
        try:
            sigs = _parse_library_decl_sigs(
                (workspace / rel).read_text(encoding="utf-8"))
        except OSError:
            continue
        for fqn in fqns:
            decl = fqn.rsplit(".", 1)[-1]
            sc = sigs.get(decl)
            if sc is None:
                continue  # def / unparsed → not an apply-canonical
            bc, concl = sc
            out.append(_LibCanon(
                fqn=fqn, module=fqn.rsplit(".", 1)[0],
                binder_count=bc, concl_tokens=_distinctive_tokens(concl)))
    _LIBRARY_INDEX_CACHE[key] = out
    return out


# Safety bound on how many Library decls a single candidate probes against
# (caps the probe's import closure — measured to dominate cost). Logged,
# never silent, when it bites. With IDF ranking a real reuse match shares
# RARE tokens → high score → ranks within the cap, so a modest K is safe.
# Calibrated by measurement (task #108).
_LIBRARY_MAX_PAIRS_PER_CAND = 25


def _eligible_library(workspace: Path, *, domain: str,
                      candidate_count: int, candidate_concl: str,
                      ) -> "list[tuple[str, str]]":
    """Library decls in `domain` that plausibly close a candidate with
    conclusion `candidate_concl` and `candidate_count` binder groups.
    Pre-filter: binder_count ≤ candidate_count (specialization direction,
    same rule as the in-problem pools) AND ≥1 shared distinctive token (so
    the probe imports only matched modules, not the whole domain). Ranked
    by overlap, capped at `_LIBRARY_MAX_PAIRS_PER_CAND`. Returns
    (module, fqn)."""
    canons = _library_canonicals(workspace, domain)
    if not canons:
        return []
    cand_tokens = _distinctive_tokens(candidate_concl)
    if not cand_tokens:
        return []
    # IDF-weighted overlap. Plain "≥1 shared token" is far too loose:
    # measured, ~40+ LinearAlgebra decls share a token (Submodule /
    # finrank / LinearMap…) with any LA sub-goal. So rank by the RARITY of
    # the shared tokens — a shared `singularValues` / `jordan` is real
    # reuse signal; a shared `Submodule` is noise. df = how many domain
    # canonicals contain the token; idf down-weights ubiquitous ones.
    n_docs = len(canons)
    df: dict[str, int] = {}
    for c in canons:
        for t in c.concl_tokens:
            df[t] = df.get(t, 0) + 1

    def _idf(t: str) -> float:
        return math.log((n_docs + 1) / (df.get(t, 0) + 1)) + 1.0

    scored: list[tuple[float, tuple[str, str]]] = []
    for c in canons:
        if c.binder_count > candidate_count:
            continue
        shared = cand_tokens & c.concl_tokens
        if not shared:
            continue
        scored.append((sum(_idf(t) for t in shared), (c.module, c.fqn)))
    scored.sort(key=lambda t: t[0], reverse=True)
    if len(scored) > _LIBRARY_MAX_PAIRS_PER_CAND:
        print(f"[dedupe] library pool ({domain}): {len(scored)} plausible "
              f"decls over cap {_LIBRARY_MAX_PAIRS_PER_CAND}; probing top "
              f"{_LIBRARY_MAX_PAIRS_PER_CAND} by token overlap", flush=True)
        scored = scored[:_LIBRARY_MAX_PAIRS_PER_CAND]
    return [mf for _, mf in scored]


def _batch_provable_via_apply(
    workspace: Path,
    problem: str,
    pairs: list[tuple[str, str, str]],
) -> list[bool]:
    """For each (cand_signature, canonical_module, canonical_fqn)
    pair, check if `apply @canonical_fqn <;> assumption` proves
    `<cand_signature>`.

    `cand_signature` is `<binders> : <conclusion>` (output of
    `_extract_full_signature`).
    `canonical_module` is the Lean module to import for canonical.
    `canonical_fqn` is the fully-qualified name to `apply @` — built by
    the caller, NOT reconstructed here. In-problem canonicals pass
    `Problems.<problem>.<thm>`; cross-problem Library decls pass
    `Library.<...>.<decl>` (whose namespace ≠ `Problems.<problem>`).

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

    # Pre-flight: materialize .olean for every canonical module we're
    # about to import. `lake env lean` does NOT cascade-build, so a
    # missing .olean trips a global "object file does not exist" error
    # that fail-opens the whole batch to all-False. Running `lake build`
    # over the unique module set ensures every canonical is on disk
    # before elaboration starts. Lake's scheduler builds independent
    # modules in parallel; first call within a daemon run pays full
    # cost (~30-60s for Jordan-deep modules), subsequent calls hit
    # cache. Best-effort: any failure here leaves the original fail-
    # open behaviour intact, so dedupe quality degrades gracefully.
    # Replaces the prior inline-in-verify-housekeeping materialization
    # (jordan_normal_form 2026-05-25: that scheme stalled the
    # dispatcher main thread N × ~30-60s on every cascade chain).
    seen_modules: set[str] = set()
    for _, mod, _ in pairs:
        if mod:
            seen_modules.add(mod)
    if seen_modules:
        from ..pipeline._lake import lake_build_modules as _lake_build_modules
        try:
            _lake_build_modules(workspace, sorted(seen_modules))
        except Exception as exc:  # noqa: BLE001 — best-effort
            print(f"[dedupe] pre-flight lake build failed "
                  f"(non-fatal): {exc}", flush=True)

    lines: list[str] = ["import Mathlib"]
    defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
    if defs_path.exists():
        lines.append(f"import Problems.{problem}.Defs")

    for mod in sorted(seen_modules):
        lines.append(f"import {mod}")

    lines.append("")
    lines.append("namespace dedupe_check")
    lines.append("")

    pair_start_lines: list[int] = []
    for i, (cand_sig, canonical_module, canonical_fqn) in enumerate(pairs):
        # canonical_fqn is the fully-qualified name to `apply @`, already
        # built by the caller. The probe does NOT reconstruct a namespace
        # from `problem`, so a Library decl (namespace `Library.<...>` ≠
        # `Problems.<problem>`) is invoked exactly like an in-problem one.
        if not canonical_fqn:
            # No fqn resolved — pair is unusable; emit a
            # syntactically-broken stub so its line attributes the error
            # to this pair only (not a global error swallowing siblings).
            pair_start_lines.append(len(lines) + 1)
            lines.append(f"-- pair {i} (no canonical fqn)")
            lines.append(f"theorem _dc_{i} : True := by trivial_unknown_tac_force_fail")
            lines.append("")
            continue
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

    # Walk error lines and partition them by which pair's range they
    # fall into. Errors outside any pair range are GLOBAL (e.g. import
    # not found, namespace mis-parse, earlier example bailing the
    # elaborator). A global error invalidates the run — Lean may have
    # stopped before reaching later pairs, so absence-of-error in their
    # line range does NOT mean unify passed. Conservative: treat all
    # pairs as False on global error.
    #
    # NB (2026-05-29 BT bug): we do NOT fast-path on rc=0. `lake env
    # lean` emits per-line `error(<kind>): ...` for tactic / elaboration
    # failures but propagates rc=0 anyway, so the old fast-path silently
    # accepted every pair when Lean had actually rejected the apply
    # body. The error-line scan below is now the sole truth-source for
    # the probe's per-pair verdict, regardless of process exit code.
    #
    # NB (task #108): this stays a COLD `lake env lean`, not the warm
    # gateway. Measured: a gateway `verify_file` of this throwaway
    # Mathlib-importing file costs ~24s EVERY call (the warm worker still
    # elaborates a fresh file's import environment from scratch; warmth
    # only helps incremental re-edits of the same slot) — no faster than
    # cold lake (~20s) and it ties up a gateway worker slot. So the cold
    # subprocess (separate process, no gateway contention) is kept.
    error_lines: set[int] = set()
    for m in _LAKE_ERR_RE.finditer(output):
        error_lines.add(int(m.group(1)))

    if not error_lines:
        # No error lines parsed from the output. Two sub-cases:
        #   - rc == 0 AND no errors → genuinely clean elaboration, every
        #     pair passed.
        #   - rc != 0 AND no errors → failure pattern is unfamiliar
        #     (Lean crashed pre-elaboration, lake env setup error, etc.);
        #     refuse all rather than silently accept.
        if rc == 0:
            return [True] * len(pairs)
        return [False] * len(pairs)

    in_any_pair = set()
    for el in error_lines:
        for i, start in enumerate(pair_start_lines):
            end = (pair_start_lines[i + 1] - 1
                   if i + 1 < len(pair_start_lines) else len(lines))
            if start <= el <= end:
                in_any_pair.add(el)
                break

    if error_lines - in_any_pair:
        # Global error present: failure is not attributable to a single
        # pair. Refuse all.
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
    """Strict ancestors of `parent_goal_id` that are PROVED and whose
    binder count ≤ `candidate_count`. Filtered to alive lineage.

    Proved-only by design: aliasing a candidate to a NOT-yet-proved
    ancestor is circular (the ancestor's own proof depends on this very
    sub-goal). Unproved ancestors — and `parent_goal_id` itself — are
    instead handled by `_eligible_self_and_unproved_ancestors` as the
    `no_progress` tier (decline-and-retry, never alias)."""
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
        "  AND g.status = 'proved' "
        "ORDER BY g.id ASC",
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


def _eligible_self_and_unproved_ancestors(
        conn: sqlite3.Connection, workspace: Path, *,
        problem: str, parent_goal_id: int,
        candidate_count: int) -> list[tuple[sqlite3.Row, str]]:
    """The `no_progress` pool: `parent_goal_id` itself PLUS its still-
    unproved (open/attempting) alive ancestors, binder count ≤
    `candidate_count`.

    A proposed sub-goal definitionally equal to one of these is a
    self-similar `X ⊢ X` decomposition — proving X by reducing to X (or
    to an ancestor whose proof in turn needs X). It can never be aliased
    (circular) and is pure no-progress, so the caller declines-and-retries
    instead of creating yet another identical goal. `parent_goal_id` is
    included because the dominant case is decomposing a goal into a
    sub-goal identical to that very goal — invisible to the ancestor walk,
    which starts ABOVE the parent."""
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
        "WHERE g.problem = ? "
        "  AND (g.id = ? OR (g.id IN alive AND g.id IN ancestors)) "
        "  AND g.status IN ('open','attempting') "
        "ORDER BY g.id ASC",
        (problem, parent_goal_id, problem, parent_goal_id),
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
      - `"alias"`: canonical is PROVED — caller should write an
        alias body and insert the candidate as `proved` aliased to
        `goal_id`.
      - `"disproved"`: canonical is disproved (agent showed a
        counterexample) — caller should decline this candidate. The
        proposed statement is already known false. `goal_id` is the
        disproved goal so the caller can surface its dead_attempt
        forensic in the decline message.
      - `"no_progress"`: candidate is definitionally the goal being
        decomposed (`parent_goal_id`) or one of its still-unproved
        ancestors — proving it from there is circular and makes no
        progress (the self-similar `X ⊢ X` decomposition). Caller should
        decline-and-RETRY: re-prompt the same agent to decompose into
        strictly smaller sub-goals or prove the goal directly. `goal_id`
        is the matched ancestor/self for the message.
      - `"library_alias"` (A — cross-problem reuse): canonical is an
        already-proved `Library/` decl (no in-DB goal). Caller writes an
        alias delegating to `library_fqn` (importing `library_module`)
        and inserts the candidate as `proved`. `goal_id` is -1 (no goal);
        the citation is `library_fqn`.
    """
    goal_id: int
    kind: str  # "alias" | "disproved" | "no_progress" | "library_alias"
    library_module: str | None = None  # set iff kind == "library_alias"
    library_fqn: str | None = None


_SLUG_DUP_SUFFIXES = ("_alias", "_2", "_3", "_4", "_5")


def _slug_match_proved(conn: sqlite3.Connection, *, problem: str,
                       candidate_slug: str,
                       parent_goal_id: int) -> int | None:
    """Tier 1 dedupe (2026-05-26 post-Jordan): cheap slug-pattern check.

    Backward agent often names a duplicate sub-goal by suffixing a
    known proved goal with `_alias` / `_2` / `_3` (e.g.
    `pushforward_d_eq` → `pushforward_d_eq_alias`,
    `jordan_add_const_diag` → `jordan_add_const_diag_2`). The kernel-
    probe Tier 2 below should catch these by signature, but is fragile
    to subtle binder reorderings and silent lake errors — Jordan's
    9 confirmed duplicate pairs all slipped through.

    This pre-check strips any known duplicate suffix and looks for a
    proved goal in the same problem with the stripped name. On hit:
    return its goal_id so the caller can alias without elaborating.
    Conservative: `_strong` is NOT stripped (different semantics —
    weak-hypothesis dropping); arbitrary `_vN` / `_new` patterns also
    not stripped to avoid false positives.

    Excludes `parent_goal_id` (anti-cycle) and alias-target goals
    (no alias chains), mirroring `_eligible_problem_proved`.
    """
    for suffix in _SLUG_DUP_SUFFIXES:
        if not candidate_slug.endswith(suffix):
            continue
        base = candidate_slug[:-len(suffix)]
        if not base:
            continue
        row = conn.execute(
            "SELECT id FROM goals "
            "WHERE problem = ? AND slug = ? AND status = 'proved' "
            "  AND id != ? AND alias_target_id IS NULL "
            "LIMIT 1",
            (problem, base, parent_goal_id),
        ).fetchone()
        if row is not None:
            return int(row["id"])
    return None


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

    # Initialize result with Tier 1 slug-pattern hits (cheap; no lake).
    # Per-candidate kernel-probe (Tier 2) below skips any candidate whose
    # slot is already filled here.
    result: list[CanonicalMatch | None] = [None] * n
    for ci, (slug, _) in enumerate(candidates):
        hit_id = _slug_match_proved(
            conn, problem=problem, candidate_slug=slug,
            parent_goal_id=parent_goal_id,
        )
        if hit_id is not None:
            result[ci] = CanonicalMatch(goal_id=hit_id, kind="alias")

    # Per-candidate eligible canonicals. Alive/proved tiers come first
    # so they take precedence on first-hit. The disproved tier is appended
    # afterwards and only contributes when no alive/proved canonical
    # exists for the candidate. Tag each row with its source kind so
    # the assembly loop below can emit the right `CanonicalMatch.kind`.
    KIND_ALIAS = "alias"
    KIND_DISPROVED = "disproved"
    KIND_NO_PROGRESS = "no_progress"
    cand_pools: list[list[tuple[sqlite3.Row, str, str]]] = []
    for ci, (slug, full_text) in enumerate(candidates):
        # Tier 1 already hit: no need to enumerate kernel-probe pool.
        if result[ci] is not None:
            cand_pools.append([])
            continue
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
        no_progress = _eligible_self_and_unproved_ancestors(
            conn, workspace, problem=problem,
            parent_goal_id=parent_goal_id, candidate_count=cand_count,
        )
        # Order = priority on first-hit: a PROVED canonical (alias) wins over
        # both a disproved precedent and a no-progress self/ancestor match —
        # if the candidate can be discharged by an existing proof, do that.
        # disproved (statement known false) outranks no_progress (retryable).
        pool: list[tuple[sqlite3.Row, str, str]] = []
        for r, t in anc + orph + cross:
            pool.append((r, t, KIND_ALIAS))
        for r, t in disproved:
            pool.append((r, t, KIND_DISPROVED))
        for r, t in no_progress:
            pool.append((r, t, KIND_NO_PROGRESS))
        cand_pools.append(pool)

    # Build flat list of pairs to check; track origin (cand_idx, row, kind).
    # Each pair: (cand_signature, canonical_module, canonical_theorem_name).
    # Canonical's module is derived from anc_row's lean_path; theorem
    # name extracted from anc_text directly (DB slug ≠ on-disk theorem
    # name in some framework-promoted / aliased cases, where the file
    # body is `def <slug> := @s<sid>` — see _THM_HEAD_RE comment).
    pairs: list[tuple[str, str, str]] = []
    # origin per pair: (cand_idx, kind, payload). payload is an sqlite Row
    # for the in-problem tiers, or a (module, fqn) tuple for the Library
    # tier (A). Kept uniform so the result loop dispatches on `kind`.
    pair_origin: list[tuple[int, str, object]] = []
    from ..pipeline._lake import lean_path_to_module
    domain = problem.split(".")[0] if "." in problem else problem
    for ci, (slug, full_text) in enumerate(candidates):
        if result[ci] is not None:
            continue  # Tier 1 slug hit already filled this slot
        cand_sig = _extract_full_signature(full_text)
        if cand_sig is None:
            continue
        for anc_row, anc_text, kind in cand_pools[ci]:
            canonical_thm = _extract_theorem_name(anc_text) or ""
            # DB stores workspace-relative lean_path strings; resolve
            # to absolute before module conversion.
            anc_lean_path = workspace / anc_row["lean_path"]
            try:
                canonical_module = lean_path_to_module(workspace, anc_lean_path)
            except (ValueError, OSError):
                continue
            # In-problem canonical: namespace is `Problems.<problem>`
            # (the sub-goal file declares `namespace Problems.<problem>`),
            # so the FQN is `Problems.<problem>.<thm>`. Empty thm → empty
            # fqn → probe emits its force-fail stub for this pair.
            canonical_fqn = (f"Problems.{problem}.{canonical_thm}"
                             if canonical_thm else "")
            pairs.append((cand_sig, canonical_module, canonical_fqn))
            pair_origin.append((ci, kind, anc_row))
        # Library tier (A) — cross-problem reuse. Appended LAST so an
        # in-problem match (alias/disproved/no_progress) shadows it on
        # first-hit: prefer local reuse, keep deps in-problem; only reach
        # to Library when nothing in-problem matches.
        cand_count = _signature_binder_count(full_text)
        cand_concl = _conclusion_of_signature(cand_sig)
        for lib_module, lib_fqn in _eligible_library(
                workspace, domain=domain, candidate_count=cand_count,
                candidate_concl=cand_concl):
            pairs.append((cand_sig, lib_module, lib_fqn))
            pair_origin.append((ci, "library_alias", (lib_module, lib_fqn)))

    if not pairs:
        # No kernel work to do (either every candidate was Tier 1-hit
        # or had no eligible pool). Still report metric for forensic.
        n_alias = sum(1 for m in result if m and m.kind == "alias")
        n_disproved = sum(1 for m in result if m and m.kind == "disproved")
        n_noprog = sum(1 for m in result if m and m.kind == "no_progress")
        print(f"[dedupe] checked {n} candidate(s) against 0 pair(s); "
              f"alias={n_alias} disproved={n_disproved} "
              f"no_progress={n_noprog} library=0 (slug-tier only)",
              flush=True)
        return result

    flags = _batch_provable_via_apply(workspace, problem, pairs)

    # First-hit per candidate. pair_origin order is alive→disproved within
    # each candidate (because cand_pools concatenates alive first), so
    # the first True flag picked up is automatically the highest-priority
    # match. An "alias" hit therefore shadows a later "disproved" hit on
    # the same candidate — the desired behavior (an alive canonical is
    # always more useful than a disproved precedent). Slot-already-filled
    # by Tier 1 is also skipped here so Tier 1 hits aren't overwritten
    # (e.g. by a disproved tier match that would change `kind`).
    for (ci, kind, payload), is_eq in zip(pair_origin, flags):
        if not is_eq:
            continue
        if result[ci] is not None:
            continue
        if kind == "library_alias":
            lib_module, lib_fqn = payload  # type: ignore[misc]
            result[ci] = CanonicalMatch(
                goal_id=-1, kind="library_alias",
                library_module=lib_module, library_fqn=lib_fqn)
        else:
            result[ci] = CanonicalMatch(
                goal_id=int(payload["id"]), kind=kind)  # type: ignore[index]
    # Lightweight metric — surfaces dedupe effectiveness in the daemon
    # log so Phase 2 design (Strategist/Forward/Librarian) has empirical
    # input on alias hit rate and disproved-collision frequency. `library`
    # is the cross-problem reuse counter (A) — the seed of the reuse
    # instrumentation. Pre-fix the entire Windows-side dedupe pipeline was
    # silently producing zeros here; this print catches any regression.
    n_alias = sum(1 for m in result if m and m.kind == "alias")
    n_disproved = sum(1 for m in result if m and m.kind == "disproved")
    n_noprog = sum(1 for m in result if m and m.kind == "no_progress")
    n_library = sum(1 for m in result if m and m.kind == "library_alias")
    print(f"[dedupe] checked {n} candidate(s) against {len(pairs)} "
          f"pair(s); alias={n_alias} disproved={n_disproved} "
          f"no_progress={n_noprog} library={n_library}", flush=True)
    return result


def build_alias_content(*, original_content: str,
                        canonical_module: str,
                        canonical_slug: str,
                        apply_expr: str | None = None) -> str:
    """Take the candidate's original sub-goal lean text and produce its
    alias version: inject `import canonical_module` and rewrite the
    sorry-stub body to delegate to canonical via tactics.

    `apply_expr` overrides what follows `apply ` in the body. In-problem
    aliases leave it None → `apply <canonical_slug>` (bare slug resolves
    because the alias file shares the canonical's `Problems.<problem>`
    namespace). The Library tier (A) passes `@<fqn>` because a Library
    decl's namespace (`Library.<...>`) is NOT open in the sub-goal file —
    only the fully-qualified name resolves.
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

    body = apply_expr if apply_expr is not None else canonical_slug
    return _SORRY_BODY_RE.sub(
        f":= by apply {body} <;> assumption",
        original_content,
        count=1,
    )


def find_shelved_revivals_for_forward(
    conn: sqlite3.Connection, workspace: Path, *,
    problem: str, forward_goal_id: int,
) -> list[int]:
    """For a freshly-committed Forward output goal X, return the list of
    shelved goal IDs in the same problem whose signatures can be
    discharged by `apply @X <;> assumption`.

    Direction note (vs `find_canonicals_batch`): here X is the canonical
    (would-be discharger) and shelved goals are candidates (would-be
    revived). At link time X's lean file may carry `:= by sorry`, but
    Lean still elaborates the declaration's type, so the alpha-equivalence
    probe is sound. The actual alias body is written later by the verify
    revival pass when X transitions to `proved`.

    Binder rule mirrors the standard alias direction: X (canonical) must
    have ≤ binders than the candidate so `apply @X` can specialize and
    let `assumption` discharge the extras.

    Returns shelved goal IDs that pass the probe. Caller is expected to
    set `S.alias_target_id = X.id` for each. Fail-open on any
    extraction / subprocess error (returns []).
    """
    x_row = conn.execute(
        "SELECT id, slug, lean_path FROM goals WHERE id = ?",
        (forward_goal_id,),
    ).fetchone()
    if x_row is None:
        return []
    try:
        x_text = (workspace / x_row["lean_path"]).read_text(encoding="utf-8")
    except OSError:
        return []
    x_thm = _extract_theorem_name(x_text)
    if not x_thm:
        return []
    from ..pipeline._lake import lean_path_to_module
    try:
        x_module = lean_path_to_module(workspace, workspace / x_row["lean_path"])
    except (ValueError, OSError):
        return []
    x_binder_count = _signature_binder_count(x_text)

    rows = conn.execute(
        "SELECT g.id, g.slug, g.lean_path FROM goals g "
        "WHERE g.problem = ? AND g.status = 'shelved' "
        "  AND g.alias_target_id IS NULL "
        "  AND g.id != ? "
        "ORDER BY g.id ASC",
        (problem, forward_goal_id),
    ).fetchall()

    pairs: list[tuple[str, str, str]] = []
    pair_origin: list[int] = []
    for r in rows:
        try:
            cand_text = (workspace / r["lean_path"]).read_text(
                encoding="utf-8")
        except OSError:
            continue
        cand_sig = _extract_full_signature(cand_text)
        if cand_sig is None or not cand_sig.strip():
            continue
        if _signature_binder_count(cand_text) < x_binder_count:
            # Candidate has fewer binders than X — `apply @X` would need
            # arguments the candidate's context can't supply via
            # `assumption`. Standard binder rule (see `_eligible_*`).
            continue
        # X is the canonical here; its file declares `namespace
        # Problems.<problem>`, so its FQN is `Problems.<problem>.<x_thm>`.
        pairs.append((cand_sig, x_module, f"Problems.{problem}.{x_thm}"))
        pair_origin.append(int(r["id"]))

    if not pairs:
        return []
    flags = _batch_provable_via_apply(workspace, problem, pairs)
    revivals = [gid for gid, ok in zip(pair_origin, flags) if ok]
    if revivals:
        print(f"[dedupe] shelved-revival probe: forward={forward_goal_id} "
              f"matched {len(revivals)} shelved goal(s) {revivals}",
              flush=True)
    return revivals
