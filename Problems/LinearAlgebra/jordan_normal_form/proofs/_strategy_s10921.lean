import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_pred_basis_to_consecutive
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_range_jordan_to_pred_basis

namespace Problems.LinearAlgebra.jordan_normal_form

-- Glue bU (Jordan basis of `range N`) up to a Jordan basis of `W`, then reindex.
-- Split the two concerns the prior all-at-once attempt conflated:
--   * `range_jordan_to_pred_basis`: the LA chain-glue — lift chain tops through N,
--     extend `ker N`, assemble a Jordan basis of W in *predecessor (π) form*
--     (no Fin-consecutiveness constraint, so the index layout is out of the way).
--   * `pred_basis_to_consecutive`: turns any (b, π) Jordan basis into the
--     consecutive-index form — this is the Fin-index layout step (reuses
--     `block_enum_consecutive` internally).
theorem s10921
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) (hN0 : N ≠ 0)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (bU : Module.Basis (Fin (Module.finrank K (LinearMap.range N))) K (LinearMap.range N))
    (hbU : ∀ j : Fin (Module.finrank K (LinearMap.range N)),
        (N.restrict h_inv) (bU j) = 0 ∨
          ∃ i : Fin (Module.finrank K (LinearMap.range N)),
            (i : ℕ) + 1 = (j : ℕ) ∧ (N.restrict h_inv) (bU j) = bU i) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i  := by
  obtain ⟨b, π, hπ⟩ := range_jordan_to_pred_basis N hN hN0 h_inv bU hbU
  exact pred_basis_to_consecutive N b π hπ

end Problems.LinearAlgebra.jordan_normal_form
