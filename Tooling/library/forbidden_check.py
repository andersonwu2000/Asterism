"""Per-Problem forbidden_lemmas blacklist check (P6.x patch 21).

Spec:
    Each Problem's META.md may declare `forbidden_lemmas: [...]` — a hard
    constraint that the framework enforces post-Builder. If the proof
    file references any forbidden lemma name, the proof is rejected; the
    goal stays open and a dead_attempts entry surfaces the violation in
    Backward's next failure_replay so the agent stops re-trying the
    same banned tactic.

Implementation (first cut):
    Word-boundary regex search over the proof file text. False positives
    are possible if a forbidden name appears in a comment or as a
    substring of an unrelated identifier — operators can switch to a
    Lean-walker (`tools/forbidden_walker.lean` walking transitive
    constants) when the textual approach drops too many real proofs.

Public API:
    check_forbidden(proof_path, forbidden_lemmas) -> list[str]
        Returns the list of forbidden lemma names that the proof file
        references (preserves the order they appear in the file). Empty
        list when nothing is matched.
"""
from __future__ import annotations

import re
from pathlib import Path


def _entry_to_pattern(entry: str) -> "re.Pattern[str]":
    """Compile a forbidden_lemmas entry into a regex.

    Two modes:
      - Exact name (no `*`): word-boundary match. `Cardinal.mk_real`
        catches `Cardinal.mk_real` but not `Cardinal.mk_realInfinite`
        and not `Real.uncountable_univ` either way (separate identifier).
      - Glob (contains `*`): each `*` becomes `[\\w.]*` (zero or more
        identifier / dot characters). Lets operators block whole
        Mathlib subtrees:
            `Cardinal.*` → catches `Cardinal.mk_real`, `Cardinal.aleph0`,
                            `Cardinal.SubMul.foo`, ...
            `Real.uncountable*` → catches `Real.uncountable`,
                            `Real.uncountable_univ`, `Real.uncountableSubmodule`
            `Mathlib.SetTheory.Cardinal.*` → catches the full prefix
                            (only useful when proof file uses fully-
                            qualified names; bare `Cardinal.*` is the
                            common Lean style)
    """
    if "*" in entry:
        parts = entry.split("*")
        body = r"[\w.]*".join(re.escape(p) for p in parts)
    else:
        body = re.escape(entry)
    # Look-around for Lean-style dotted identifier boundary: dot does
    # NOT count as a word break, so we treat dotted paths as contiguous.
    return re.compile(r"(?<![\w.])" + body + r"(?![\w])")


def check_forbidden(
    proof_path: str | Path,
    forbidden_lemmas: frozenset[str] | set[str] | list[str],
) -> list[str]:
    """Return the list of forbidden lemma names referenced in the proof.

    Each entry in *forbidden_lemmas* is either an exact name or a glob
    (`*` wildcards expanding to `[\\w.]*`). A glob match reports as
    `"<actual_name> (glob: <pattern>)"` so dead_attempts surfaces the
    specific name in addition to the rule that caught it.

    Comment-string false positives: a forbidden name embedded in a
    comment (e.g. ``-- could try Real.uncountable here``) is still a
    match. Operators should keep blacklisted names out of comments
    inside .lean files, or upgrade to the Lean-walker (P7+).
    """
    if not forbidden_lemmas:
        return []
    p = Path(proof_path)
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8", errors="replace")
    found: list[str] = []
    seen: set[str] = set()
    for lemma in forbidden_lemmas:
        pattern = _entry_to_pattern(lemma)
        matches = pattern.findall(text)
        if not matches:
            continue
        # Dedup matches per-pattern so a name appearing 3 times reports once.
        for actual in dict.fromkeys(matches):  # preserves first-seen order
            if "*" in lemma and actual != lemma:
                key = f"{actual} (glob: {lemma})"
            else:
                key = lemma
            if key not in seen:
                found.append(key)
                seen.add(key)
    return found
