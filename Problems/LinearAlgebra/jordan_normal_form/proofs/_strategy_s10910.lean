import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_blockdiag_submatrix_isjordan
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_reindex_tomatrix_eq_blockdiag_submatrix

namespace Problems.LinearAlgebra.jordan_normal_form

-- Reindex the block-diagonal basis `b` by the order-iso `e` to a `Fin (finrank V)` basis.
-- `reindex_tomatrix_eq_blockdiag_submatrix`: the reindexed basis' matrix equals
--   `(blockDiagonal' Mμ).submatrix e e` (pure `toMatrix`/`reindex` bookkeeping).
-- `blockdiag_submatrix_isjordan`: that submatrix is Jordan form — block-wise from `hjor` and the
--   consecutive-index order property `he` (pure matrix combinatorics, no `T`/basis).
-- Combine: rewrite the goal matrix to the submatrix, then apply the Jordan-form fact.
theorem s10910
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    {n : K → ℕ}
    [Fintype ((μ : K) × Fin (n μ))]
    (b : Module.Basis ((μ : K) × Fin (n μ)) K V)
    (Mμ : (μ : K) → Matrix (Fin (n μ)) (Fin (n μ)) K)
    (hb : LinearMap.toMatrix b b T = Matrix.blockDiagonal' Mμ)
    (hjor : ∀ μ : K, IsJordanForm (Mμ μ))
    (e : Fin (Module.finrank K V) ≃ ((μ : K) × Fin (n μ)))
    (he : ∀ p q : Fin (Module.finrank K V), (e p).1 = (e q).1 →
        ((((e p).2 : ℕ) + 1 = ((e q).2 : ℕ)) ↔ ((p : ℕ) + 1 = (q : ℕ)))) :
    ∃ b' : Module.Basis (Fin (Module.finrank K V)) K V,
      IsJordanForm (LinearMap.toMatrix b' b' T) := by
  refine ⟨b.reindex e.symm, ?_⟩
  have h1 := reindex_tomatrix_eq_blockdiag_submatrix T b Mμ hb hjor e he
  rw [h1]
  exact blockdiag_submatrix_isjordan T b Mμ hb hjor e he

end Problems.LinearAlgebra.jordan_normal_form
