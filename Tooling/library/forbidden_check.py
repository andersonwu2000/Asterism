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


def check_forbidden(
    proof_path: str | Path,
    forbidden_lemmas: frozenset[str] | set[str] | list[str],
) -> list[str]:
    """Return the list of forbidden lemma names referenced in the proof.

    Word-boundary match: `Cardinal.mk_real` does not match
    `Cardinal.mk_realInfinite` (different identifier). Inverse-direction
    issue: a forbidden name like `Real.uncountable` won't catch
    `Real.uncountable_univ` (different lemma). Operators list explicitly.

    Comment-string false positives: a forbidden name embedded in a
    comment (e.g. ``-- could try Real.uncountable here``) is still a
    match. Caller documentation guides users to keep blacklisted names
    out of comments inside .lean files, or upgrade to the Lean-walker.
    """
    if not forbidden_lemmas:
        return []
    p = Path(proof_path)
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8", errors="replace")
    found: list[str] = []
    for lemma in forbidden_lemmas:
        # `\b` doesn't quite line up with Lean's identifier grammar
        # (dots aren't word boundaries) — use look-around so the match
        # fails when surrounded by `\w` or `.` (treat the dotted path as
        # one contiguous identifier).
        pattern = re.compile(
            r"(?<![\w.])" + re.escape(lemma) + r"(?![\w])"
        )
        if pattern.search(text):
            found.append(lemma)
    return found
