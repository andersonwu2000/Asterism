---
problem: Putnam.putnam_1977_a1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1977_a1 — imported from PutnamBench

Original theorem: `putnam_1977_a1` (Putnam 1977 A1).

## Statement

Show that if four distinct points of the curve $y = 2x^4 + 7x^3 + 3x - 5$ are collinear, then their average $x$-coordinate is some constant $k$. Find $k$.

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
