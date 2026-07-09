---
problem: Putnam.putnam_2005_a3
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2005_a3 — imported from PutnamBench

Original theorem: `putnam_2005_a3` (Putnam 2005 A3).

## Statement

Let $p(z)$ be a polynomial of degree $n$ all of whose zeros have absolute value $1$ in the complex plane. Put $g(z)=p(z)/z^{n/2}$. Show that all zeros of $g'(z)=0$ have absolute value $1$.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
