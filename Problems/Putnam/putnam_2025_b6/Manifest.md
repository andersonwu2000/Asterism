---
problem: Putnam.putnam_2025_b6
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2025_b6 — imported from PutnamBench

Original theorem: `putnam_2025_b6` (Putnam 2025 B6).

## Statement

Let $\mathbb{N} = \{1, 2, 3, \ldots\}$. Find the largest real constant $r$ such that
there exists a function $g: \mathbb{N} \to \mathbb{N}$ such that
$$g(n+1) - g(n) \geq (g(g(n)))^r$$
for all $n \in \mathbb{N}$.

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
