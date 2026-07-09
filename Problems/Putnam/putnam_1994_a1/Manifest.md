---
problem: Putnam.putnam_1994_a1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1994_a1 — imported from PutnamBench

Original theorem: `putnam_1994_a1` (Putnam 1994 A1).

## Statement

Suppose that a sequence $a_1,a_2,a_3,\dots$ satisfies $0< a_n \leq a_{2n}+a_{2n+1}$ for all $n \geq 1$. Prove that the series $\sum_{n=1}^\infty a_n$ diverges.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
