---
problem: Putnam.putnam_1962_a3
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1962_a3 — imported from PutnamBench

Original theorem: `putnam_1962_a3` (Putnam 1962 A3).

## Statement

Let $\triangle ABC$ be a triangle in the Euclidean plane, with points $P$, $Q$, and $R$ lying on segments $\overline{BC}$, $\overline{CA}$, $\overline{AB}$ respectively such that $$\frac{AQ}{QC} = \frac{BR}{RA} = \frac{CP}{PB} = k$$ for some positive constant $k$. If $\triangle UVW$ is the triangle formed by parts of segments $\overline{AP}$, $\overline{BQ}$, and $\overline{CR}$, prove that $$\frac{[\triangle UVW]}{[\triangle ABC]} = \frac{(k - 1)^2}{k^2 + k + 1},$$ where $[\triangle]$ denotes the area of the triangle $\triangle$.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
