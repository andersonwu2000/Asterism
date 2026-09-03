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
import re
import sqlite3
from pathlib import Path
from typing import NamedTuple

from ..state import db
from .dedupe_probe import (  # noqa: F401 — re-exported: tests and
    _BATCH_TIMEOUT_SEC, _LAKE_ERR_RE, _MAX_ERRORS_RE,  # the conftest stub
    _batch_provable_via_apply, _batch_statement_defeq,  # bind dedupe.<name>
    _max_errors_cutoff,
)


# Signature extractor: matches ONLY a real `theorem` / `lemma` DECL HEAD
# (lemma is just an alias for theorem in Lean 4). Signature-based aliasing
# is theorem-only by design: aliasing rewrites the body to a Prop tactic
# `apply <canonical> <;> assumption` (proof-irrelevance makes same-type ⇒
# aliasable). It is deliberately NOT extended to `def`/`structure`/`class`/
# `abbrev`/`instance`: those are DATA, where same-type ≠ same-value, so
# `def A := B` would silently redefine A as a different construction.
#
# The regex is LINE-ANCHORED (`re.MULTILINE`, `^` + optional attrs/modifiers)
# and callers strip comments first, so a stray `theorem`/`lemma` token in a
# comment can never seed a probe. Root-cause of the 2026-07-03 mv_delta
# incident: the old `\b(?:theorem|lemma)\s+\S+` searched raw text and, for a
# `def` candidate, matched the Forward seed's comment `-- Write ONE forward
# lemma here` → `lemma here` → a garbage signature was probed against 163
# canonicals and (via a second build_alias_content defect) false-aliased δ
# to an unrelated support-membership lemma. A `def` candidate now yields
# no signature → `find_canonicals_batch` forms no alias pair.
_THM_HEAD_RE = re.compile(
    r"^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
    r"(?:(?:private|protected|scoped|local|nonrec)[ \t]+)*"
    r"(?:theorem|lemma)[ \t]+\S+",
    re.MULTILINE,
)
_SORRY_BODY_RE = re.compile(r":=\s*by\s+sorry")
def _strip_comments(text: str) -> str:
    """Remove Lean line (`-- …`) and block (`/- … -/`) comments so the
    signature extractor anchors on a real decl head, never comment prose.
    Mirrors `proof_store._strip_comments`."""
    text = re.sub(r"/-.*?-/", "", text, flags=re.S)
    return re.sub(r"--[^\n]*", "", text)


def _signature_binder_count(text: str) -> int:
    """Count top-level binder groups before the type colon.

    `theorem foo (x : Nat) {α} [Inhabited α] : T := ...` → 3.
    Returns 0 for a non-theorem/lemma decl (e.g. a `def` candidate), whose
    head the extractor deliberately does not match.
    """
    text = _strip_comments(text)
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


def _normalized_signature(text: str) -> str | None:
    """`_extract_full_signature` with whitespace collapsed — the tier-0
    identity key (2026-08-08).

    Why a STRING check in front of a kernel probe: the Lean probes below
    can be blind. `apply @canonical <;> assumption` unifies the
    CONCLUSION first, so a statement whose conclusion does not mention
    every binder leaves those metavariables unconstrained, `assumption`
    mis-assigns them, and the probe reports "not equal" — deterministically
    — for a pair that is byte-identical. That is not hypothetical: goal
    7499 was a character-for-character copy of its own parent 7486, the
    probe ran on the pair at commit time and returned False, and the copy
    entered the tree (whence a spent route, five shelved goals and two
    Strategist wakes spent catching it by hand).

    The normalization is deliberately CONSERVATIVE — comments (via
    `_extract_full_signature`) and whitespace only. NOT alpha-renaming,
    NOT notation folding: the property that makes a tier-0 hit safe to
    act on WITHOUT the kernel is `normalized-equal ⇒ literally the same
    statement ⇒ defeq`, and every cleverer rule trades that certainty for
    recall. Recall is what the kernel probes are for; this tier exists to
    be the one that cannot be wrong.
    """
    sig = _extract_full_signature(text)
    if sig is None:
        return None
    flat = " ".join(sig.split())
    return flat or None


def _extract_full_signature(text: str) -> str | None:
    """Return `<binders> : <conclusion>` portion of the first theorem.

    Given `theorem foo (M : T) (h : U) : Sat M := proof`, returns
    `(M : T) (h : U) : Sat M`. The result is suitable for converting
    into `∀`-form via `_to_forall_form`. Returns None for a non-theorem/
    lemma decl (a `def` candidate) — signature-aliasing is theorem-only.

    The body `:=` is found by `assemble.body_assign_index` — the ONE
    scanner that knows a `let x : T := v` inside the TYPE owns the next
    top-level `:=`. This function used to stop at the first depth-0
    `:=` unconditionally, so every statement opening with a `let`-chain
    vocabulary preamble truncated to the same few-word fragment — and
    tier-0, whose whole safety argument is "normalized-equal ⇒
    literally the same statement", then judged DIFFERENT statements
    identical. Measured 2026-08-17 on union_closed: a sub-goal proving
    ONE conjunct of goal 7912's three-way `∧` was rejected `no_progress
    ≡ goal 7912` because both signatures truncated to
    `: let M : Nat → Finset (Fin 6)`; the same collapse burned 15+
    attempts across four Fin-census bricks (g7784/7812/7894/7912),
    each retry renamed and re-rejected. `assemble` had fixed this exact
    parse for the seeded-skeleton splitter on 2026-07-19 (PutnamCmp
    b6_1) — this was the second spelling of that knowledge, unfixed.
    """
    text = _strip_comments(text)
    m = _THM_HEAD_RE.search(text)
    if not m:
        return None
    from ..state.assemble import body_assign_index
    end = body_assign_index(text, m.end())
    if end < 0:
        return None
    return text[m.end():end].strip() or None


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
# (see _THM_HEAD_RE for the case background). Same hardening as
# _THM_HEAD_RE (cbe5bc3's bug FAMILY, second instance — task #6): line-
# anchored + comment-stripped by the extractor. Canonical files ALWAYS
# open with the Strategist's prose annotation block, and prose containing
# `theorem X` / `def Y` used to seed the probe with a garbage name — the
# probe then failed against the WRONG fqn and a legitimate dedupe hit was
# silently missed (false negative: the sub-goal gets re-proved from
# scratch instead of aliased).
_THM_NAME_RE = re.compile(
    r"^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
    r"(?:(?:noncomputable|private|protected|scoped|local|nonrec)[ \t]+)*"
    r"(?:theorem|lemma|def)[ \t]+(\S+)",
    re.MULTILINE,
)


def _sig_shape(sig: str) -> str:
    """`<binders> : <type>` of a full signature with the decl kind + name
    dropped and whitespace collapsed — the statement-shape key the REUSE
    tier compares (task #6). The apply-probe stays deliberately loose
    (2026-05-11: rfl → apply, hypothesis-extension tolerance — right for
    the alias tiers whose written body literally IS the apply); the reuse
    REWRITE however assumes statement identity (the citation keeps the
    candidate's arg list), so it gets this stricter syntactic gate on top."""
    s = re.sub(r"\s+", " ", sig).strip()
    m = re.match(r"(?:theorem|lemma|def)\s+\S+\s*(.*)$", s)
    return m.group(1).strip() if m else s


def _extract_theorem_name(text: str) -> str | None:
    """Extract the declared name from the first line-anchored
    `theorem|lemma|def <name>` DECL HEAD in the file (comments stripped
    first — a mention in the annotation block is not a declaration).
    Returns None if none found."""
    m = _THM_NAME_RE.search(_strip_comments(text))
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
# Source of truth = the DB (v18): bridged problems' placed decls via
# `db.bridged_library_index`; module = fqn minus last segment.
# ---------------------------------------------------------------------


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


# Per-(file, mtime) signature-parse cache for the NULL-signature fallback:
# a file whose decls lack a DB signature is parsed once per content version.
# The DB read itself is cheap and uncached (v18 — was: a whole-pool cache
# keyed on INDEX.md mtime, invalidated wholesale by every bridge rewrite).
_LIB_SIG_FILE_CACHE: "dict[tuple[str, float], dict]" = {}


def _library_canonicals(conn, workspace: Path,
                        domain: str) -> "list[_LibCanon]":
    """All theorem/lemma Library decls in `domain`, with binder count +
    conclusion tokens. v18: rows come from the DB (bridged problems'
    placed decls — `db.bridged_library_index`); binder/conclusion come
    from the kernel-true `signature` column when backfilled, else from
    parsing the .lean file (per-file mtime cache) — today's behavior as
    the fallback."""
    from ..state import db as _db
    by_file: "dict[str, list]" = {}
    for rows in _db.bridged_library_index(conn).values():
        for r in rows:
            rel = str(r["target_file"] or "")
            fqn = str(r["target_name"] or "")
            if not rel or not fqn:
                continue
            parts = rel.replace("\\", "/").split("/")
            if len(parts) >= 2 and parts[0] == "Library" and (
                    domain == "*" or parts[1] == domain):
                by_file.setdefault(rel, []).append(r)
    out: list[_LibCanon] = []
    for rel, rows in by_file.items():
        file_sigs: "dict | None" = None
        for r in rows:
            fqn = str(r["target_name"])
            decl = fqn.rsplit(".", 1)[-1]
            sig = r["signature"] if "signature" in r.keys() else None
            kind = (str(r["decl_kind"]) if "decl_kind" in r.keys()
                    and r["decl_kind"] else "")
            if sig:
                if kind and kind not in ("thm",):
                    continue  # data decl → not an apply-canonical
                # ppSignature shape: `<name> <binders> : <conclusion>` —
                # strip the leading name, reuse the existing sig parsers.
                body = str(sig)
                if body.startswith(fqn):
                    body = body[len(fqn):].strip()
                else:
                    body = body.split(" ", 1)[1] if " " in body else body
                bc = _signature_binder_count(f"theorem x {body} := sorry")
                concl = _conclusion_of_signature(body)
                if not kind and not concl:
                    continue  # unparsable + kind unknown → skip like before
                out.append(_LibCanon(
                    fqn=fqn, module=fqn.rsplit(".", 1)[0],
                    binder_count=bc,
                    concl_tokens=_distinctive_tokens(concl)))
                continue
            # NULL signature → parse the file once (mtime-cached).
            if file_sigs is None:
                fp = workspace / rel
                try:
                    key = (str(fp), fp.stat().st_mtime)
                except OSError:
                    file_sigs = {}
                else:
                    hit = _LIB_SIG_FILE_CACHE.get(key)
                    if hit is None:
                        try:
                            hit = _parse_library_decl_sigs(
                                fp.read_text(encoding="utf-8"))
                        except OSError:
                            hit = {}
                        if len(_LIB_SIG_FILE_CACHE) > 512:
                            _LIB_SIG_FILE_CACHE.clear()
                        _LIB_SIG_FILE_CACHE[key] = hit
                    file_sigs = hit
            sc = file_sigs.get(decl)
            if sc is None:
                continue  # def / unparsed → not an apply-canonical
            bc, concl = sc
            out.append(_LibCanon(
                fqn=fqn, module=fqn.rsplit(".", 1)[0],
                binder_count=bc, concl_tokens=_distinctive_tokens(concl)))
    return out


# Safety bound on how many Library decls a single candidate probes against
# (caps the probe's import closure — measured to dominate cost). Logged,
# never silent, when it bites. With IDF ranking a real reuse match shares
# RARE tokens → high score → ranks within the cap, so a modest K is safe.
# Calibrated by measurement (task #108).
_LIBRARY_MAX_PAIRS_PER_CAND = 25


def _eligible_library(conn, workspace: Path, *, domain: str,
                      candidate_count: int, candidate_concl: str,
                      ) -> "list[tuple[str, str]]":
    """Library decls in `domain` that plausibly close a candidate with
    conclusion `candidate_concl` and `candidate_count` binder groups.
    Pre-filter: binder_count ≤ candidate_count (specialization direction,
    same rule as the in-problem pools) AND ≥1 shared distinctive token (so
    the probe imports only matched modules, not the whole domain). Ranked
    by overlap, capped at `_LIBRARY_MAX_PAIRS_PER_CAND`. Returns
    (module, fqn)."""
    canons = _library_canonicals(conn, workspace, domain)
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


def _sig_split_binders(sig: str) -> "tuple[str, str] | None":
    """Split a full signature `<binders> : <conclusion>` at the TOP-LEVEL
    colon (depth-aware over ()/{}/[]/⦃⦄ — binder types contain colons).
    Returns (binders, conclusion) or None if no top-level colon."""
    depth = 0
    for i, ch in enumerate(sig):
        if ch in "({[⦃":
            depth += 1
        elif ch in ")}]⦄":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            if i + 1 < len(sig) and sig[i + 1] == "=":
                return None  # `:=` — malformed for a signature
            return sig[:i].strip(), sig[i + 1:].strip()
    return None


def _binder_bracket_seq(sig: str) -> "str | None":
    """The TOP-LEVEL binder bracket sequence of a signature — one char
    per binder group: '(' explicit, '{' implicit, '[' instance, '⦃'
    strict-implicit. Binder NAMES and types are ignored (paraphrase-
    free); nesting inside a binder's type is skipped depth-aware
    ((h : (A → B) ∧ C) is ONE group). Interface metadata like
    explicitness is invisible to kernel defeq, so P1's statement-link
    checks it here textually.

    KNOWN-CONSERVATIVE: `theorem A (x : ℕ) : P x` vs
    `theorem B : ∀ x : ℕ, P x` have the same call interface but
    different bracket sequences → judged different → the candidate
    mints as novel. Deliberate: a conservative miss costs one duplicate,
    a false link breaks the patch rewrite. Not a bug (do not re-report).
    """
    split = _sig_split_binders(sig)
    if split is None:
        return None
    binders, _ = split
    seq: list[str] = []
    depth = 0
    for ch in binders:
        if ch in "({[⦃":
            if depth == 0:
                seq.append(ch)
            depth += 1
        elif ch in ")}]⦄":
            depth = max(0, depth - 1)
    return "".join(seq)


def _forall_form(sig: str) -> "str | None":
    """`<binders> : <conclusion>` → the Prop term `∀ <binders>, <concl>`
    (or just the conclusion when there are no binders) — the shape the
    statement-defeq probe compares."""
    split = _sig_split_binders(sig)
    if split is None:
        return None
    binders, concl = split
    if not binders:
        return concl
    return f"∀ {binders}, {concl}"


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
    # Phase 6 — alive seed is the shared root ∪ detached fragment (the old
    # root-only copy dropped detached Forward goals from the alive filter).
    rows = conn.execute(
        f"WITH RECURSIVE {db.ALIVE_CTE_PER_PROBLEM}"
        ", ancestors(id) AS ("
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
        (problem, problem, parent_goal_id, problem),
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
    # Phase 6 — shared root ∪ detached alive seed (see _eligible_ancestors).
    rows = conn.execute(
        f"WITH RECURSIVE {db.ALIVE_CTE_PER_PROBLEM}"
        ", ancestors(id) AS ("
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
        (problem, problem, parent_goal_id, problem, parent_goal_id),
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


def _eligible_problem_reusable(conn: sqlite3.Connection, workspace: Path, *,
                               problem: str, parent_goal_id: int,
                               candidate_count: int,
                               exclude_ids: set[int],
                               ) -> list[tuple[sqlite3.Row, str]]:
    """Non-terminal, NON-proved goals in the same Problem that a candidate
    sub-goal can REUSE instead of duplicating: `open` / `attempting` /
    `pending_strategist_review` / `shelved`. This is the #2 case — two
    branches (or a branch + a parked goal) landing on the same statement
    where the strict-ancestor / orphan / proved-cross-branch pools see
    nothing (the canonical isn't proved).

    Unlike the proved pool, the canonical is NOT yet proved, so it cannot
    be immediately aliased. The caller turns the candidate into a CITATION
    of the canonical and lets the existing cite-gate link-and-wait (and
    revive, if `shelved`); the canonical proving later satisfies the citer.

    Anti-cycle (critical): excludes `parent_goal_id` AND every ANCESTOR of
    it. Linking to an ancestor is circular — the ancestor transitively
    waits for this candidate's proof. (Proved ancestors are safe and
    handled by the proved pool; here the canonical is unproved.) Also
    excludes alias goals and `exclude_ids` (already pooled — no
    double-emit / no status-kind ambiguity).
    """
    anc_rows = conn.execute(
        "WITH RECURSIVE ancestors(id) AS ("
        "  SELECT s.goal_id FROM strategies s"
        "    JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        "    WHERE ss.subgoal_id = ?"
        "  UNION"
        "  SELECT s.goal_id FROM strategies s"
        "    JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        "    JOIN ancestors a ON a.id = ss.subgoal_id"
        ") SELECT id FROM ancestors",
        (parent_goal_id,),
    ).fetchall()
    block = ({parent_goal_id}
             | {int(r["id"]) for r in anc_rows}
             | set(exclude_ids))
    placeholders = ",".join("?" for _ in block)
    rows = conn.execute(
        f"SELECT g.id, g.statement, g.lean_path, g.status FROM goals g "
        f"WHERE g.problem = ? "
        f"  AND g.status IN "
        f"      ('open','attempting','pending_strategist_review','shelved') "
        f"  AND g.alias_target_id IS NULL "
        f"  AND g.id NOT IN ({placeholders}) "
        f"ORDER BY g.id ASC",
        (problem, *block),
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
    enum split (see `docs/archive/design/phase2/pipelines.md` §4.1) moved soft-terminal
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
      - `"reuse"` (#2 — in-problem NON-proved twin): canonical is an
        `open`/`attempting`/`pending_strategist_review`/`shelved` goal in
        the same problem (a cross-branch or parked twin), NOT proved.
        Cannot be immediately aliased; the caller turns the candidate
        into a CITATION of `goal_id` and lets the cite-gate link-and-wait
        (revive if shelved) — the canonical proving later satisfies it.
        A SPENT twin (attempts exhausted, or a wrong-context decline)
        is one of these: it had its own blocking tier until 2026-09-04,
        when goal `dead` retired and every park became linkable, so the
        cheap link-and-wait subsumes the old decline-with-forensics
        (task #112; b6 2026-07-12 showed the block shadowing a linkable
        twin of the same statement and re-opening the inject→abort
        churn the reuse tier exists to collapse).
    """
    goal_id: int
    kind: str  # "alias" | "disproved" | "no_progress" | "library_alias" | "reuse"
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

    # Tier 1 slug-pattern hits (cheap; no lake) — since task #6 these are
    # PROBE-CONFIRMED like every other alias, not blind: the slug
    # convention ("collision → rename `_2`, keep the statement
    # byte-identical") is exactly when the statement is SUPPOSED to match,
    # but nothing enforced it — a `_2` whose statement had drifted got
    # blind-aliased and exploded far downstream at the parent strategy's
    # lake build. The hit now seeds the TOP of the candidate's probe pool
    # (keeps its historical first priority, rides the existing batch call
    # for ~zero cost); a probe miss falls through to the other tiers
    # instead of forcing a bogus alias. Side effect: a `def` candidate has
    # no theorem signature → forms no pair → can no longer be blind-
    # aliased by name (closing Tier 1's copy of the def-blind hole
    # cbe5bc3 closed for Tier 2 — data defs are never alias-safe).
    result: list[CanonicalMatch | None] = [None] * n
    tier1_rows: "list[sqlite3.Row | None]" = [None] * n
    for ci, (slug, _) in enumerate(candidates):
        hit_id = _slug_match_proved(
            conn, problem=problem, candidate_slug=slug,
            parent_goal_id=parent_goal_id,
        )
        if hit_id is not None:
            tier1_rows[ci] = conn.execute(
                "SELECT id, lean_path FROM goals WHERE id = ?",
                (hit_id,)).fetchone()

    # Per-candidate eligible canonicals. Alive/proved tiers come first
    # so they take precedence on first-hit. The disproved tier is appended
    # afterwards and only contributes when no alive/proved canonical
    # exists for the candidate. Tag each row with its source kind so
    # the assembly loop below can emit the right `CanonicalMatch.kind`.
    KIND_ALIAS = "alias"
    KIND_DISPROVED = "disproved"
    KIND_NO_PROGRESS = "no_progress"
    KIND_REUSE = "reuse"
    cand_pools: list[list[tuple[sqlite3.Row, str, str]]] = []
    # Reuse pool kept separate so it can be appended to `pairs` AFTER the
    # Library tier — low priority (a proved alias always beats linking
    # an unproved twin). Aligned 1:1 with `candidates`.
    cand_reusable: list[list[tuple[sqlite3.Row, str]]] = []
    for ci, (slug, full_text) in enumerate(candidates):
        sig = _extract_full_signature(full_text)
        if sig is None or not sig.strip():
            # No theorem signature (e.g. a `def` candidate) → no probe
            # pool at all; a Tier 1 slug hit is dropped here too (data
            # defs are never alias-safe — see tier1_rows comment).
            cand_pools.append([])
            cand_reusable.append([])
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
        # Tier 1 slug hit seeds the FRONT of the pool (first-hit priority
        # preserved) — probe-confirmed, see the comment at tier1_rows.
        t1 = tier1_rows[ci]
        if t1 is not None:
            try:
                t1_text = (workspace / t1["lean_path"]).read_text(
                    encoding="utf-8")
                pool.insert(0, (t1, t1_text, KIND_ALIAS))
            except OSError:
                pass
        cand_pools.append(pool)
        # Reuse tier (#2): non-proved alive/parked cross-branch twin.
        # Exclude everything already pooled so a goal is classified once
        # (and never as both no_progress and reuse).
        reuse_exclude = (seen_ids
                         | {int(r["id"]) for r, _ in cross}
                         | {int(r["id"]) for r, _ in disproved}
                         | {int(r["id"]) for r, _ in no_progress})
        cand_reusable.append(_eligible_problem_reusable(
            conn, workspace, problem=problem,
            parent_goal_id=parent_goal_id, candidate_count=cand_count,
            exclude_ids=reuse_exclude,
        ))

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
    # Task #6: the Library pool spans ALL domains — the old hard filter
    # (problem's first dotted segment) structurally blocked cross-domain
    # reuse (a Geometry problem could never see a LinearAlgebra keystone;
    # de Rham currents-style work spans analysis+geometry+algebra). Cost
    # stays bounded: the IDF-weighted token-overlap prefilter now ranks
    # over the whole corpus (rarity weighting improves with it) and the
    # per-candidate pair cap is unchanged.
    domain = "*"
    for ci, (slug, full_text) in enumerate(candidates):
        cand_sig = _extract_full_signature(full_text)
        if cand_sig is None:
            continue
        # ── Tier 0: syntactic identity, decided without Lean ──────────
        # Normalized-equal signatures ARE the same statement, so no probe
        # can legitimately disagree — and one of them demonstrably does
        # (see `_normalized_signature`). Checked before the pool is turned
        # into probe pairs, in pool order, so it inherits the same
        # first-hit priority the kernel tiers use.
        cand_norm = _normalized_signature(full_text)
        if cand_norm is not None and result[ci] is None:
            for anc_row, anc_text, kind in cand_pools[ci]:
                # BLOCKING verdicts only. A tier-0 hit says "these two
                # signature TEXTS are the same", which is not quite the
                # same as "these two TYPES are the same": identical text
                # in two files can elaborate differently under different
                # `open` / `variable` scopes. That gap is harmless when
                # the verdict is "reject this sub-goal, decompose
                # differently" (worst case, one wasted retry) and is NOT
                # harmless when the verdict GRANTS a proof — an alias
                # makes the candidate inherit the canonical's proof, so
                # it stays kernel-confirmed (task #6: a `_2` slug
                # collision must never alias on a name, and it must not
                # alias on a string either).
                if kind not in (KIND_NO_PROGRESS, KIND_DISPROVED):
                    continue
                if _normalized_signature(anc_text) != cand_norm:
                    continue
                # `slug` is not in every pool query's SELECT — name the
                # canonical by whatever the row actually carries.
                _keys = anc_row.keys()
                _name = (anc_row["slug"] if "slug" in _keys
                         else f"goal {anc_row['id']}")
                print(f"[dedupe] tier-0 identity: candidate {ci} "
                      f"({slug}) is byte-equal to `{_name}` "
                      f"({kind}) — no probe needed", flush=True)
                result[ci] = CanonicalMatch(
                    goal_id=int(anc_row["id"]), kind=kind)
                break
        # ── Tier 0 for the reuse pool (owner ruling 2026-08-29): a twin
        # whose normalized statement IS the candidate's is a reuse hit on
        # the spot. The kernel is not asked, so the twin's module — a
        # shelved leftover more often than not — is never imported for
        # a question the text already settled.
        if result[ci] is None and cand_norm is not None:
            for reuse_row, reuse_text in cand_reusable[ci]:
                if _normalized_signature(reuse_text) != cand_norm:
                    continue
                print(f"[dedupe] tier-0 identity: candidate {ci} ({slug}) "
                      f"is byte-equal to twin goal {int(reuse_row['id'])} "
                      f"({reuse_row['status']}) — reuse-link, no probe",
                      flush=True)
                result[ci] = CanonicalMatch(
                    goal_id=int(reuse_row["id"]), kind=KIND_REUSE)
                break
        if result[ci] is not None:
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
                conn, workspace, domain=domain, candidate_count=cand_count,
                candidate_concl=cand_concl):
            pairs.append((cand_sig, lib_module, lib_fqn))
            pair_origin.append((ci, "library_alias", (lib_module, lib_fqn)))
        # Reuse tier (#2) — appended LAST (lowest priority): a proved
        # alias (in-problem or Library) is always preferable to linking
        # an unproved twin. Same FQN construction as the in-problem pools.
        for reuse_row, reuse_text in cand_reusable[ci]:
            # Task #6: reuse pairs are additionally gated on statement
            # SHAPE equality — the rewrite assumes more than the (kept-
            # deliberately-loose) apply-probe grants; two recorded
            # incidents of apply-hit-on-mismatched-twin → citation
            # rewrite → commit lake `Function expected`. Conservative:
            # a binder-name difference forgoes the reuse (the sub-goal
            # just commits as novel — safe direction). See _sig_shape.
            twin_sig = _extract_full_signature(reuse_text)
            if twin_sig is None or _sig_shape(cand_sig) != _sig_shape(
                    twin_sig):
                continue
            reuse_thm = _extract_theorem_name(reuse_text) or ""
            try:
                reuse_module = lean_path_to_module(
                    workspace, workspace / reuse_row["lean_path"])
            except (ValueError, OSError):
                continue
            reuse_fqn = (f"Problems.{problem}.{reuse_thm}"
                         if reuse_thm else "")
            pairs.append((cand_sig, reuse_module, reuse_fqn))
            pair_origin.append((ci, KIND_REUSE, reuse_row))

    # NB: no early return on empty `pairs` — the P1 statement-defeq pass
    # below can still have work (a shelved twin whose shape mismatches
    # forms no apply pair). `_batch_provable_via_apply([])` returns [].
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
        # `is_eq is None` = the probe never answered (timeout / OSError /
        # metaprogramming skip). Treated as "no hit" exactly as before —
        # dedupe is an optimisation, never a soundness verdict — but it
        # is COUNTED and reported, so a scan that silently did nothing
        # can no longer masquerade as a scan that found nothing.
        if is_eq is not True:
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
    # P1 (2026-07-11, b6 twin-minting churn): statement-defeq reuse for
    # SHELVED twins the binder-verbatim shape gate missed. The paraphrase
    # dimension (binder renames, notation drift) is exactly what walled
    # runs produce round after round — ~15 fresh-slug twins of one shelved
    # crux, each costing a review wake + a 15-min agent. Two-layer match:
    # bracket-sequence interface pre-filter (cheap, textual) + kernel rfl
    # defeq of the full ∀-types (authority — the byte fast-path was
    # demoted to a pre-filter on teammate review: no kernel bypass).
    # Downstream is the ordinary reuse path: citation rewrite + cite-gate
    # link-and-wait (a ConfirmShelve-parked twin links WITHOUT revival).
    defeq_pairs: list[tuple[str, str, str]] = []
    defeq_origin: list[tuple[int, sqlite3.Row]] = []
    for ci, (slug, full_text) in enumerate(candidates):
        if result[ci] is not None:
            continue
        cand_sig = _extract_full_signature(full_text)
        if cand_sig is None:
            continue
        cand_seq = _binder_bracket_seq(cand_sig)
        cand_forall = _forall_form(cand_sig)
        if cand_seq is None or cand_forall is None:
            continue
        for reuse_row, reuse_text in cand_reusable[ci]:
            if str(reuse_row["status"]) != "shelved":
                continue
            twin_sig = _extract_full_signature(reuse_text)
            if twin_sig is None:
                continue
            if _sig_shape(cand_sig) == _sig_shape(twin_sig):
                continue  # already probed via the strict reuse path above
            if _binder_bracket_seq(twin_sig) != cand_seq:
                continue  # call interface differs — rewrite would break
            twin_forall = _forall_form(twin_sig)
            if twin_forall is None:
                continue
            try:
                twin_module = lean_path_to_module(
                    workspace, workspace / reuse_row["lean_path"])
            except (ValueError, OSError):
                continue
            defeq_pairs.append((cand_forall, twin_forall, twin_module))
            defeq_origin.append((ci, reuse_row))
    n_defeq = 0
    if defeq_pairs:
        for (ci, row), ok in zip(
                defeq_origin,
                _batch_statement_defeq(workspace, problem, defeq_pairs)):
            if ok and result[ci] is None:
                result[ci] = CanonicalMatch(
                    goal_id=int(row["id"]), kind="reuse")
                n_defeq += 1
                print(f"[dedupe] statement-defeq: "
                      f"{candidates[ci][0]} ≡ shelved twin "
                      f"{int(row['id'])} — reuse-link, no new sub-goal",
                      flush=True)

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
    n_reuse = sum(1 for m in result if m and m.kind == "reuse")
    n_unchecked = sum(1 for f in flags if f is None)
    print(f"[dedupe] checked {n} candidate(s) against {len(pairs)} "
          f"pair(s); alias={n_alias} disproved={n_disproved} "
          f"no_progress={n_noprog} library={n_library} reuse={n_reuse} "
          f"(defeq={n_defeq})"
          + (f" — WARNING: {n_unchecked} pair(s) UNCHECKED (probe did "
             f"not answer; a duplicate here would not have been seen)"
             if n_unchecked else ""),
          flush=True)
    return result


def leading_decl_attrs(text: str, slug: str) -> str:
    """The `@[...]` attribute block immediately preceding the
    `theorem/def/instance/abbrev <slug>` declaration in `text`, each
    attribute normalized onto its own line (trailing newline), or '' if
    none.

    Lets the alias-finalization writers (`prune._canonical_alias_content`,
    `_skeleton.promote_to_alias`) carry e.g. `@[instance]` from a
    Prop-class root's stub (`@[instance] theorem main : T := by sorry`)
    through the `def <slug> := @…` rewrite. Returns '' for the common
    plain-`theorem` case, so non-instance roots finalize byte-for-byte
    as before. Matches both same-line (`@[instance] theorem main`) and
    own-line (`@[instance]\\ntheorem main`) forms, and is idempotent over
    an already-aliased `@[instance] def main := …`.
    """
    m = re.search(
        r"((?:@\[[^\]]*\][ \t]*\n?[ \t]*)+)"
        r"(?:theorem|def|instance|abbrev)\s+" + re.escape(slug) + r"\b",
        text,
    )
    if not m:
        return ""
    return "".join(a + "\n" for a in re.findall(r"@\[[^\]]*\]", m.group(1)))


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
