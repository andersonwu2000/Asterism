---
problem: Analysis.inner_zero_iff_smul
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# inner_zero_iff_smul — orthogonality iff equal-norm shifts in every scalar direction

## Statement
∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X] (x y : X),
  inner ℝ x y = 0 ↔ ∀ α : ℝ, ‖x + α • y‖ = ‖x - α • y‖

## Lemma hints
- `Mathlib.Analysis.InnerProductSpace.Basic` — inner product API
- `norm_add_pow_two_real`, `norm_sub_pow_two_real` — `‖x ± αy‖²` expansion in real inner product
- `real_inner_smul_right` — `inner x (α • y) = α * inner x y`
- `sq_eq_sq'` / `pow_left_injective` — equal squares ⇒ equal norms
- `eq_zero_of_mul_self_eq_zero` — for the reverse direction's algebraic close

## Strategic notes
Two directions, both via expanding `‖x ± αy‖² = ‖x‖² ± 2α·⟨x,y⟩ + α²‖y‖²`:

- **Forward** `⟨x,y⟩ = 0 → ∀α, ‖x+αy‖ = ‖x-αy‖`. Substitute `⟨x,y⟩=0` into
  the squared-norm expansion; the `±2α·⟨x,y⟩` term vanishes, leaving the
  same expression on both sides. Take square roots (norms are non-negative).

- **Reverse** `(∀α, ‖x+αy‖ = ‖x-αy‖) → ⟨x,y⟩ = 0`. Pick a specific α to
  force the `4α·⟨x,y⟩` cross term to zero. The trick: `α := ⟨x,y⟩` (or
  `α := 1` works in real inner product since `⟨x,y⟩ ∈ ℝ` already). Equal
  squared norms then give `α · ⟨x,y⟩ = 0`, which combined with the choice
  of `α` yields `⟨x,y⟩ = 0` directly.

The "for all α" universal makes this strictly more general than the
single-α Pythagorean identity Mathlib has — don't try to look up an
existing iff with this exact shape; build it from the squared-norm
expansion.
