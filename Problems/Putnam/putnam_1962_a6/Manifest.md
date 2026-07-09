---
problem: Putnam.putnam_1962_a6
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1962_a6 — imported from PutnamBench

Original theorem: `putnam_1962_a6` (Putnam 1962 A6).

## Statement

Let $S$ be a set of rational numbers such that whenever $a$ and $b$ are members of $S$, so are $a+b$ and $ab$, and having the property that for every rational number $r$ exactly one of the following three statements is true: \[ r \in S, -r \in S, r = 0. \] Prove that $S$ is the set of all positive rational numbers.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
