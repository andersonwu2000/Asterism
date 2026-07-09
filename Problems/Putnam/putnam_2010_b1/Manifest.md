---
problem: Putnam.putnam_2010_b1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2010_b1 — imported from PutnamBench

Original theorem: `putnam_2010_b1` (Putnam 2010 B1).

## Statement

Is there an infinite sequence of real numbers $a_1, a_2, a_3, \dots$ such that \[ a_1^m + a_2^m + a_3^m + \cdots = m \] for every positive integer $m$?

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
