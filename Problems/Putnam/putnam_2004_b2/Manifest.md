---
problem: Putnam.putnam_2004_b2
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2004_b2 — imported from PutnamBench

Original theorem: `putnam_2004_b2` (Putnam 2004 B2).

## Statement

Let $m$ and $n$ be positive integers. Show that $\frac{(m+n)!}{(m+n)^{m+n}}<\frac{m!}{m^m}\frac{n!}{n^n}$.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
