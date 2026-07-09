---
problem: Putnam.putnam_2025_a1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2025_a1 — imported from PutnamBench

Original theorem: `putnam_2025_a1` (Putnam 2025 A1).

## Statement

Let $m_0$ and $n_0$ be distinct positive integers. For every positive integer $k$,
define $m_k$ and $n_k$ to be the relatively prime positive integers such that
$$\frac{m_k}{n_k} = \frac{2m_{k-1} + 1}{2n_{k-1} + 1}.$$
Prove that $2m_k + 1$ and $2n_k + 1$ are relatively prime for all but finitely many
positive integers $k$.

The formal statement is pinned in `Root.lean` (`theorem main`).
No solution abbrev — pure proof task.

## Strategic notes

Imported via `Benchmarks/putnambench/adapter.py` from
trishullab/PutnamBench @ a23d8e6. No per-problem hints —
benchmark integrity. The pinned statement is never edited;
if you believe it is FALSE, that is what `AttemptDisproof` /
`RequestUserAmend` are for.
