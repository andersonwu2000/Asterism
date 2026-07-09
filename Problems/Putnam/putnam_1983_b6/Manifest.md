---
problem: Putnam.putnam_1983_b6
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1983_b6 — imported from PutnamBench

Original theorem: `putnam_1983_b6` (Putnam 1983 B6).

## Statement

Let $n$ be a positive integer and let $\alpha \neq 1$ be a complex $(2n + 1)\textsuperscript{th}$ root of unity. Prove that there always exist polynomials $p(x)$, $q(x)$ with integer coefficients such that $p(\alpha)^2 + q(\alpha)^2 = -1$.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
