---
problem: Putnam.putnam_2025_a2
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2025_a2 — imported from PutnamBench

Original theorem: `putnam_2025_a2` (Putnam 2025 A2).

## Statement

Find the largest real number $a$ and the smallest real number $b$ such that
$$ax(\pi - x) \le \sin x \le bx(\pi - x)$$
for all $x$ in the interval $[0, \pi]$.

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
