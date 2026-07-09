---
problem: Putnam.putnam_1982_b2
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_1982_b2 — imported from PutnamBench

Original theorem: `putnam_1982_b2` (Putnam 1982 B2).

## Statement

Let $A(x, y)$ denote the number of points $(m, n)$ with integer coordinates $m$ and $n$ where $m^2 + n^2 \le x^2 + y^2$. Also, let $g = \sum_{k = 0}^{\infty} e^{-k^2}$. Express the value $$\int_{-\infty}^{\infty}\int_{-\infty}^{\infty} A(x, y)e^{-x^2 - y^2} dx dy$$ as a polynomial in $g$.

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
