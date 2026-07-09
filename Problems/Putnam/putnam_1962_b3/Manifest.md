---
problem: Putnam.putnam_1962_b3
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1962_b3 — imported from PutnamBench

Original theorem: `putnam_1962_b3` (Putnam 1962 B3).

## Statement

Let $S$ be a convex region in the Euclidean plane, containing the origin, for which every ray from the origin has at least one point outside $S$. Assuming that either the origin is an interior point of $S$ or $S$ is topologically closed, prove that $S$ is bounded.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
