---
problem: Putnam.putnam_1962_b1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1962_b1 — imported from PutnamBench

Original theorem: `putnam_1962_b1` (Putnam 1962 B1).

## Statement

Let $x^{(n)} = x(x-1)\cdots(x-n+1)$ for $n$ a positive integer and let $x^{(0)} = 1.$ Prove that \[ (x+y)^{(n)} = \sum_{k=0}^n {n \choose k} x^{(k)} y^{(n-k)}. \]

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
