---
problem: Putnam.putnam_2025_a4
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2025_a4 — imported from PutnamBench

Original theorem: `putnam_2025_a4` (Putnam 2025 A4).

## Statement

Find the minimal value of $k$ such that there exist $k$-by-$k$ real matrices
$A_1, \ldots, A_{2025}$ with the property that $A_i A_j = A_j A_i$ if and only if
$|i - j| \in \{0, 1, 2024\}$.

The formal statement is pinned in `Root.lean` (`theorem main`).
The `_solution` abbrev in `Defs.lean` carries the OFFICIAL
answer (upstream ships it as a comment; this matches the
standard solutions-replaced evaluation protocol — the task
is proving, not answer-finding).

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
