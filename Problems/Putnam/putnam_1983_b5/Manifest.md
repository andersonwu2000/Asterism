---
problem: Putnam.putnam_1983_b5
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1983_b5 — imported from PutnamBench

Original theorem: `putnam_1983_b5` (Putnam 1983 B5).

## Statement

Define $\left\lVert x \right\rVert$ as the distance from $x$ to the nearest integer. Find $\lim_{n \to \infty} \frac{1}{n} \int_{1}^{n} \left\lVert \frac{n}{x} \right\rVert \, dx$. You may assume that $\prod_{n=1}^{\infty} \frac{2n}{(2n-1)} \cdot \frac{2n}{(2n+1)} = \frac{\pi}{2}$.

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
