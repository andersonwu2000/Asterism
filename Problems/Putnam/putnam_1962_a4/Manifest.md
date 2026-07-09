---
problem: Putnam.putnam_1962_a4
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1962_a4 — imported from PutnamBench

Original theorem: `putnam_1962_a4` (Putnam 1962 A4).

## Statement

Assume that $\lvert f(x) \rvert \le 1$ and $\lvert f''(x) \rvert \le 1$ for all $x$ on an interval of length at least 2. Show that $\lvert f'(x) \rvert \le 2$ on the interval.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
