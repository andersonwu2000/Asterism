---
problem: Putnam.putnam_2025_b1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2025_b1 — imported from PutnamBench

Original theorem: `putnam_2025_b1` (Putnam 2025 B1).

## Statement

Suppose that each point in the plane is colored either red or green, subject to the following
condition: For every three noncollinear points $A$, $B$, $C$ of the same color, the center of the
circle passing through $A$, $B$, $C$ is also this color. Prove that all points of the plane are the
same color.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
