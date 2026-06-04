import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs

namespace Problems.LinearAlgebra.normal_diagonalization

-- Direct leaf proof: the flag subspace `span (b '' Iic j)` is T-invariant.
-- Reduce `span ≤ comap T span` to its generators (`Submodule.span_le`); each
-- generator `b k` (k ≤ j) satisfies `T (b k) ∈ span (b '' Iic k) ⊆ span (b '' Iic j)`
-- via the adapted hypothesis `hb` + span/image/Iic monotonicity. No sub-goals.
theorem s11546 {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V]
    [FiniteDimensional ℂ V] (T : V →ₗ[ℂ] V)
    (b : Module.Basis (Fin (Module.finrank ℂ V)) ℂ V)
    (hb : ∀ j : Fin (Module.finrank ℂ V),
        T (b j) ∈ Submodule.span ℂ (b '' Set.Iic j))
    (j : Fin (Module.finrank ℂ V)) (v : V)
    (hv : v ∈ Submodule.span ℂ (b '' Set.Iic j)) :
    T v ∈ Submodule.span ℂ (b '' Set.Iic j)  := by
  have key : Submodule.span ℂ (b '' Set.Iic j) ≤
      (Submodule.span ℂ (b '' Set.Iic j)).comap T := by
    rw [Submodule.span_le]
    rintro _ ⟨k, hk, rfl⟩
    simp only [Submodule.mem_comap, SetLike.mem_coe]
    exact Submodule.span_mono (Set.image_mono (Set.Iic_subset_Iic.mpr hk)) (hb k)
  exact key hv

end Problems.LinearAlgebra.normal_diagonalization
