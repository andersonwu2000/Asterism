---
problem: Putnam.putnam_1983_a6
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1983_a6 — imported from PutnamBench

Original theorem: `putnam_1983_a6` (Putnam 1983 A6).

## Statement

Let $T$ be the triangle with vertices $(0, 0)$, $(a, 0)$, and $(0, a)$. Find $\lim_{a \to \infty} a^4 \exp(-a^3) \int_T \exp(x^3+y^3) \, dx \, dy$.

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
