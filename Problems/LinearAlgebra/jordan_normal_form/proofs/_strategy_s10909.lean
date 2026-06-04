import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_block_enum_of_card

namespace Problems.LinearAlgebra.jordan_normal_form

-- Drop all linear-algebra context: the goal is pure index combinatorics on the sigma fintype.
-- Basis `b` gives `finrank K V = card ((μ:K) × Fin (n μ))`, rewriting the parent's
-- `Fin (finrank V)` into `Fin (card)`; the single sub-goal `block_enum_of_card` (stated over
-- `Fin (card)`, with no T / b / Mμ / V) then supplies the contiguous-in-order enumeration.
-- Strictly simpler: it sheds 6 hypotheses and the FiniteDimensional layer, leaving `n : K → ℕ`.
theorem s10909
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    {n : K → ℕ}
    [Fintype ((μ : K) × Fin (n μ))]
    (b : Module.Basis ((μ : K) × Fin (n μ)) K V)
    (Mμ : (μ : K) → Matrix (Fin (n μ)) (Fin (n μ)) K)
    (hb : LinearMap.toMatrix b b T = Matrix.blockDiagonal' Mμ)
    (hjor : ∀ μ : K, IsJordanForm (Mμ μ)) :
    ∃ e : Fin (Module.finrank K V) ≃ ((μ : K) × Fin (n μ)),
      ∀ p q : Fin (Module.finrank K V), (e p).1 = (e q).1 →
        ((((e p).2 : ℕ) + 1 = ((e q).2 : ℕ)) ↔ ((p : ℕ) + 1 = (q : ℕ)))  := by
  -- `finrank_eq_card_basis b` rewrites `Fin (finrank V)` to `Fin (card)`; then the
  -- index-combinatorics core `block_enum_of_card` (no T/matrices) supplies the enumeration.
  have hcard : Module.finrank K V = Fintype.card ((μ : K) × Fin (n μ)) :=
    Module.finrank_eq_card_basis b
  rw [hcard]
  exact block_enum_of_card

end Problems.LinearAlgebra.jordan_normal_form
