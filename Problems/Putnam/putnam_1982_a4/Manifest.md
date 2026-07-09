---
problem: Putnam.putnam_1982_a4
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1982_a4 — imported from PutnamBench

Original theorem: `putnam_1982_a4` (Putnam 1982 A4).

## Statement

Assume that the system of simultaneous differentiable equations \[y' = -z^3, z' = y^3\] with the initial conditions $y(0) = 1, z(0) = 0$ has a unique solution $y = f(x), z = g(x)$ defined for all real $x$. Prove that there exists a positive constant $L$ such that for all real $x$, \[f(x) + L = f(x), g(x + L) = g(x).\]

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
