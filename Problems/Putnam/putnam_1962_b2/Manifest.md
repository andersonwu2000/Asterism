---
problem: Putnam.putnam_1962_b2
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1962_b2 — imported from PutnamBench

Original theorem: `putnam_1962_b2` (Putnam 1962 B2).

## Statement

Let $\mathbb{S}$ be the set of all subsets of the natural numbers. Prove the existence of a function $f : \mathbb{R} \to \mathbb{S}$ such that $f(a) \subset f(b)$ whenever $a < b$.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
