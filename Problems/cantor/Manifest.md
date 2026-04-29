---
problem: cantor
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas:
  - Function.cantor_surjective
  - Cardinal.cantor
---

# cantor — Freek 100 #63 reformulated to constructive existential

## Statement
∀ f : ℕ → Set ℕ, ∃ S : Set ℕ, ∀ n : ℕ, f n ≠ S

## Difficulty
3

## Mathlib hints
- `Set.ext`, `Set.mem_setOf_eq`
- `iff_not_self` — proves `¬(p ↔ ¬p)`
- `Set.eq_of_mem_iff_mem`

## Strategic notes
Mathlib's `Function.cantor_surjective` proves `¬Surjective` form which is
classically equivalent but not 1:1 with this constructive existential,
and is listed forbidden anyway. Build the diagonal witness explicitly:

  S := { n : ℕ | n ∉ f n }

For each n, derive a contradiction from assuming `f n = S`: this gives
`n ∈ f n ↔ n ∈ S ↔ n ∉ f n`, which is `p ↔ ¬p` — false by `iff_not_self`.

Expected 1-2 layer Backward decomposition. Sub-goal is a propositional-
logic lemma `∀ p : Prop, ¬(p ↔ ¬p)` (closeable by `tactic_try`).
