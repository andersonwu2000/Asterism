---
problem: PutnamCmp.putnam_2025_b6_1
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: false
---

# Putnam.putnam_2025_b6_1 — Putnam 2025 B6, Seed-Prover statement

Original theorem: `putnam_2025_b6` (Putnam 2025 B6). Same informal
problem as sibling `Putnam.putnam_2025_b6`; this variant pins the
formal statement from the Seed-Prover 1.5 Putnam 2025 release
(ByteDance-Seed/Seed-Prover) — `g : ℕ+ → ℕ+` encoding, answer
`(1/4 : ℝ)` inline — for cross-encoding comparison runs. File
scaffold (imports/namespace/`main`) is ours; the theorem TYPE is
byte-faithful to upstream.

## Statement

Let $\mathbb{N} = \{1, 2, 3, \ldots\}$. Find the largest real constant $r$ such that
there exists a function $g: \mathbb{N} \to \mathbb{N}$ such that
$$g(n+1) - g(n) \geq (g(g(n)))^r$$
for all $n \in \mathbb{N}$.

The formal statement is pinned in `Root.lean` (`theorem main`); the
official answer (1/4) is inline in the statement, per upstream
(solutions-replaced evaluation protocol — the task is proving, not
answer-finding).

## Strategic notes

Statement imported from Seed-Prover 1.5 upstream, unedited. No
per-problem hints — benchmark integrity. The pinned statement is
never edited; if you believe it is FALSE, that is what
`AttemptDisproof` / `RequestUserAmend` are for.
