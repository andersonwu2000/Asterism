---
problem: PutnamCmp.putnam_2025_a5
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2025_a5 — imported from PutnamBench

Original theorem: `putnam_2025_a5` (Putnam 2025 A5).

## Statement

Let $n$ be an integer with $n \ge 2$. For a sequence $s = (s_1, \ldots, s_{n-1})$ where each
$s_i = \pm 1$, let $f(s)$ be the number of permutations $(a_1, \ldots, a_n)$ of $\{1, 2, \ldots, n\}$
such that $s_i(a_{i+1} - a_i) > 0$ for all $i$. For each $n$, determine the sequences $s$ for which
$f(s)$ is maximal.

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
