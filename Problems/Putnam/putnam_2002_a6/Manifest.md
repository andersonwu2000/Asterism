---
problem: Putnam.putnam_2002_a6
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2002_a6 — imported from PutnamBench

Original theorem: `putnam_2002_a6` (Putnam 2002 A6).

## Statement

Fix an integer $b \geq 2$. Let $f(1) = 1$, $f(2) = 2$, and for each
$n \geq 3$, define $f(n) = n f(d)$, where $d$ is the number of
base-$b$ digits of $n$. For which values of $b$ does
\[
\sum_{n=1}^\infty \frac{1}{f(n)}
\]
converge?

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
