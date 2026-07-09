---
problem: Putnam.putnam_1962_a2
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1962_a2 — imported from PutnamBench

Original theorem: `putnam_1962_a2` (Putnam 1962 A2).

## Statement

Find every real-valued function $f$ whose domain is an interval $I$ (finite or infinite) having 0 as a left-hand endpoint, such that for every positive member $x$ of $I$ the average of $f$ over the closed interval $[0, x]$ is equal to the geometric mean of the numbers $f(0)$ and $f(x)$.

The formal statement is pinned in `Root.lean` (`theorem main`).
The `_solution` abbrev in `Defs.lean` carries the OFFICIAL
answer (upstream ships it as a comment; this matches the
standard solutions-replaced evaluation protocol — the task
is proving, not answer-finding).

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
