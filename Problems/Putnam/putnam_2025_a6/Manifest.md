---
problem: Putnam.putnam_2025_a6
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2025_a6 — imported from PutnamBench

Original theorem: `putnam_2025_a6` (Putnam 2025 A6).

## Statement

Let $b_0 = 0$ and, for $n \ge 0$, define $b_{n+1} = 2b_n^2 + b_n + 1$.
For each $k \ge 1$, show that $b_{2^{k+1}} - 2b_{2^k}$ is divisible by $2^{2k+2}$
but not by $2^{2k+3}$.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
