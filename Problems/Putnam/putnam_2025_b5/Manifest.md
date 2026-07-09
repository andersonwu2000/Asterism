---
problem: Putnam.putnam_2025_b5
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2025_b5 — imported from PutnamBench

Original theorem: `putnam_2025_b5` (Putnam 2025 B5).

## Statement

Let $p$ be a prime number greater than 3. For each $k \in \{1, \ldots, p-1\}$,
let $I(k) \in \{1, 2, \ldots, p-1\}$ be such that $k \cdot I(k) \equiv 1 \pmod{p}$.
Prove that the number of integers $k \in \{1, \ldots, p-2\}$ such that
$I(k+1) < I(k)$ is greater than $p/4 - 1$.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
