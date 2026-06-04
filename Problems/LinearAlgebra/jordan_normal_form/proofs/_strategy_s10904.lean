import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_jordan_block_enumeration
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_reindex_blockdiag_to_jordan

namespace Problems.LinearAlgebra.jordan_normal_form

-- Reindex a block-diagonal (per-block Jordan) basis to a `Fin (finrank V)` global Jordan basis.
-- `jordan_block_enumeration`: there is an enumeration `e : Fin (finrank V) ≃ Σ μ, Fin (n μ)` laying
--   the blocks out contiguously and in-order — i.e. within a block, `Fin`-positions are consecutive
--   iff the within-block indices are (the order-isomorphism property `he`).
-- `reindex_blockdiag_to_jordan`: given such an `e`, the reindexed basis `b.reindex e.symm` has matrix
--   `blockDiagonal' Mμ ∘ e`, whose Jordan form follows from `hjor` block-wise plus `he`.
-- First sub-goal is pure index combinatorics on the sigma fintype (no T / matrices in its content);
-- second is matrix bookkeeping (`toMatrix_reindex` + `blockDiagonal'_apply` + case split).
theorem s10904
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    {n : K → ℕ}
    [Fintype ((μ : K) × Fin (n μ))]
    (b : Module.Basis ((μ : K) × Fin (n μ)) K V)
    (Mμ : (μ : K) → Matrix (Fin (n μ)) (Fin (n μ)) K)
    (hb : LinearMap.toMatrix b b T = Matrix.blockDiagonal' Mμ)
    (hjor : ∀ μ : K, IsJordanForm (Mμ μ)) :
    ∃ b' : Module.Basis (Fin (Module.finrank K V)) K V,
      IsJordanForm (LinearMap.toMatrix b' b' T)  := by
  obtain ⟨e, he⟩ := jordan_block_enumeration T b Mμ hb hjor
  exact reindex_blockdiag_to_jordan T b Mμ hb hjor e he



end Problems.LinearAlgebra.jordan_normal_form
