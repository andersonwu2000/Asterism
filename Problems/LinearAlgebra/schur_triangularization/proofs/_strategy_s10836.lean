import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_flag_adapted_basis_exists

namespace Problems.LinearAlgebra.schur_triangularization

-- Reduce to building a flag-adapted basis (pure linear algebra, no T): a basis b
-- with span(b '' Set.Iic j) = W (j.val + 1). T-invariance of W (j.val + 1) then
-- transports T (b j) into that span, since b j ∈ W (j.val + 1).
theorem s10836 :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V)
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ i, ∀ v ∈ W i, T v ∈ W i) →
      ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
        ∀ j : Fin (Module.finrank K V),
          T (b j) ∈ Submodule.span K (b '' Set.Iic j)  := by
  intro K _ V _ _ _ T W hW0 hWmono hWdim hWinv
  have h_flag_adapted_basis_exists := flag_adapted_basis_exists W hW0 hWmono hWdim
  obtain ⟨b, hspan⟩ := h_flag_adapted_basis_exists
  refine ⟨b, fun j => ?_⟩
  have hbj_in_W : b j ∈ W (j.val + 1) := by
    rw [← hspan j]
    exact Submodule.subset_span ⟨j, Set.mem_Iic.mpr le_rfl, rfl⟩
  have hTbj_in_W : T (b j) ∈ W (j.val + 1) := hWinv _ _ hbj_in_W
  rw [← hspan j] at hTbj_in_W
  exact hTbj_in_W
end Problems.LinearAlgebra.schur_triangularization
