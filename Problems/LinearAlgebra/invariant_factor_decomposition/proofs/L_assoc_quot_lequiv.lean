import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- assoc_quot_lequiv: Associated elements yield equal principal ideals, hence a quotient equiv.
-- Extracts unit witness from `Associated`, proves span equality, applies `Submodule.quotEquivOfEq`.
-- entry_kind: Builder
theorem assoc_quot_lequiv {R : Type*} [CommRing R] {a b : R} (h : Associated a b) :
    Nonempty ((R ⧸ Submodule.span R {a}) ≃ₗ[R] (R ⧸ Submodule.span R {b})) := by
  obtain ⟨u, hu⟩ := h
  have hspan : Submodule.span R {a} = Submodule.span R {b} := by
    apply le_antisymm
    · rw [Submodule.span_singleton_le_iff_mem]
      refine Submodule.mem_span_singleton.mpr ⟨↑u⁻¹, ?_⟩
      simp only [smul_eq_mul]
      rw [← hu]
      have hinv : (↑u⁻¹ : R) * ↑u = 1 := u.inv_mul
      calc (↑u⁻¹ : R) * (a * ↑u) = a * (↑u⁻¹ * ↑u) := by ring
        _ = a := by rw [hinv, mul_one]
    · rw [Submodule.span_singleton_le_iff_mem]
      refine Submodule.mem_span_singleton.mpr ⟨↑u, ?_⟩
      simp only [smul_eq_mul]
      rw [mul_comm, hu]
  exact ⟨Submodule.quotEquivOfEq _ _ hspan⟩

end Problems.LinearAlgebra.invariant_factor_decomposition
