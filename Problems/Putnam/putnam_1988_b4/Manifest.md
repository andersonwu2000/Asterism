---
problem: Putnam.putnam_1988_b4
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1988_b4 — imported from PutnamBench

Original theorem: `putnam_1988_b4` (Putnam 1988 B4).

## Statement

Prove that if $\sum_{n=1}^\infty a_n$ is a convergent series of positive real numbers, then so is $\sum_{n=1}^\infty (a_n)^{n/(n+1)}$.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
