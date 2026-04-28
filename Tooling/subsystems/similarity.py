"""Statement similarity metrics (P3 C23).

Token Jaccard chosen as primary metric per spike-008 D-08-1
(threshold=0.85, balance precision/recall on synthetic IH-trap fixtures).
Identifier overlap retained as secondary signal for future Strategist
work (P7); not consumed in P3.

Public API:
    token_jaccard(s1, s2) -> float in [0.0, 1.0]
    parent_subgoal_max_similarity(parent_statement, subgoal_statements)
        -> float in [0.0, 1.0]

The latter is the IH-trap signal Backward writes into
`strategies.parent_subgoal_max_similarity` at commit time. P3 stores it;
P7 Strategist reads it as one decision input.
"""
from __future__ import annotations

import re
from typing import Iterable


# Lean keywords / structural words to strip from identifier-overlap
# (kept here so the Strategist subsystem can import the same set later).
_LEAN_KEYWORDS: frozenset[str] = frozenset({
    "theorem", "lemma", "def", "example", "by", "exact", "intro", "intros",
    "apply", "have", "let", "show", "from", "fun", "λ", "match", "with",
    "if", "then", "else", "do", "return", "where", "section", "namespace",
    "end", "open", "import", "set_option", "structure", "class", "instance",
    "Type", "Prop", "Sort", "true", "false", "True", "False",
})


def _tokenize(s: str) -> list[str]:
    """Split on whitespace + punctuation; keep alphanumeric tokens + single
    operator chars. Mirrors spike-008 fixture _tokenize for consistency."""
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_'\.]*|[^\s\w]", s)
    return [t for t in tokens if t.strip()]


def token_jaccard(s1: str, s2: str) -> float:
    """Jaccard similarity on the bag-of-token sets (de-duplicated)."""
    t1 = set(_tokenize(s1))
    t2 = set(_tokenize(s2))
    if not t1 and not t2:
        return 1.0
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / len(t1 | t2)


def parent_subgoal_max_similarity(
    parent_statement: str,
    subgoal_statements: Iterable[str],
) -> float:
    """Return the maximum token_jaccard between parent and any subgoal.

    Empty `subgoal_statements` → 0.0 (no IH-trap risk to flag).
    Used by Backward._commit to populate
    `strategies.parent_subgoal_max_similarity`. Strategist (P7) compares
    the result against `ih_trap_similarity_threshold` (default 0.85 per
    spike-008 D-08-1) plus the recurring-unproductive count to decide
    early `blocked_pipelines` injection.
    """
    sims = [token_jaccard(parent_statement, s) for s in subgoal_statements]
    return max(sims) if sims else 0.0
