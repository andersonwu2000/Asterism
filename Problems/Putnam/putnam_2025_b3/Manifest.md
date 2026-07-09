---
problem: Putnam.putnam_2025_b3
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2025_b3 — imported from PutnamBench

Original theorem: `putnam_2025_b3` (Putnam 2025 B3).

## Statement

Suppose $S$ is a nonempty set of positive integers with the property that if $n$ is in $S$,
then every positive divisor of $2025^n - 15^n$ is in $S$. Must $S$ contain all positive integers?

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
