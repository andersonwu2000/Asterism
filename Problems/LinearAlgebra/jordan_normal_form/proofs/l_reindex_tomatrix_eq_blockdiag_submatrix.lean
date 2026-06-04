import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- reindex_tomatrix_eq_blockdiag_submatrix: reindexing a block-diagonal basis by e gives
-- (blockDiagonal' Mμ).submatrix e e, via Basis.reindex repr/apply bookkeeping.
-- entry_kind: Builder
theorem reindex_tomatrix_eq_blockdiag_submatrix
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
    LinearMap.toMatrix (b.reindex e.symm) (b.reindex e.symm) T
      = (Matrix.blockDiagonal' Mμ).submatrix e e := by
  rw [← hb]
  ext i j
  simp only [Matrix.submatrix_apply, LinearMap.toMatrix_apply]
  rw [Module.Basis.reindex_apply]
  have hrepr : ∀ (v : V), (b.reindex e.symm).repr v i = b.repr v (e i) := fun v => by
    simp [Module.Basis.reindex, Finsupp.domLCongr_apply]
  rw [hrepr, Equiv.symm_symm]


end Problems.LinearAlgebra.jordan_normal_form
