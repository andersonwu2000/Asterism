---
problem: Putnam.putnam_1983_a3
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1983_a3 — imported from PutnamBench

Original theorem: `putnam_1983_a3` (Putnam 1983 A3).

## Statement

Let $p$ be in the set $\{3,5,7,11,\dots\}$ of odd primes and let $F(n)=1+2n+3n^2+\dots+(p-1)n^{p-2}$. Prove that if $a$ and $b$ are distinct integers in $\{0,1,2,\dots,p-1\}$ then $F(a)$ and $F(b)$ are not congruent modulo $p$, that is, $F(a)-F(b)$ is not exactly divisible by $p$.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
