---
problem: Putnam.putnam_1962_b5
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1962_b5 — imported from PutnamBench

Original theorem: `putnam_1962_b5` (Putnam 1962 B5).

## Statement

Prove that for every integer $n$ greater than 1: \[ \frac{3n+1}{2n+2} < \left( \frac{1}{n} \right)^n + \left(\frac{2}{n} \right)^n + \cdots + \left(\frac{n}{n} \right)^n < 2. \]

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
