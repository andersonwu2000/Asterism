---
problem: Putnam.putnam_1962_b6
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1962_b6 — imported from PutnamBench

Original theorem: `putnam_1962_b6` (Putnam 1962 B6).

## Statement

Let \[ f(x) = \sum_{k=0}^n a_k \sin kx + b_k \cos kx, \] where $a_k$ and $b_k$ are constants. Show that, if $\lvert f(x) \rvert \le 1$ for $0 \le x \le 2 \pi$ and $\lvert f(x_i) \rvert = 1$ for $0 \le x_1 < x_2 < \cdots < x_{2n} < 2 \pi$, then $f(x) = \cos (nx + a)$ for some constant $a$.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
