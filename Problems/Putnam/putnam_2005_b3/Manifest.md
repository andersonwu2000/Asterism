---
problem: Putnam.putnam_2005_b3
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2005_b3 — imported from PutnamBench

Original theorem: `putnam_2005_b3` (Putnam 2005 B3).

## Statement

Find all differentiable functions $f:(0,\infty) \to (0,\infty)$ for which there is a positive real number $a$ such that $f'(\frac{a}{x})=\frac{x}{f(x)}$ for all $x>0$.

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
