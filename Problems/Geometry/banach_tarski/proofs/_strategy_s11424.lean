import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- T preserves W (W.map T ≤ W) and T is a linear equiv, so finrank is preserved;
-- in finite dimension a submodule contained in W with equal finrank IS W, hence
-- W.map T = W, so every w ∈ W has a preimage y ∈ W. Direct (no sub-goals).
theorem s11424
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (T : F ≃ₗᵢ[ℝ] F) (W : Submodule ℝ F)
    (hW : ∀ x ∈ W, T x ∈ W) :
    ∀ w ∈ W, ∃ y ∈ W, T y = w  := by
  have hmap : W.map T.toLinearEquiv.toLinearMap ≤ W := by
    rintro x ⟨y, hy, rfl⟩
    exact hW y hy
  have hfin : Module.finrank ℝ (W.map T.toLinearEquiv.toLinearMap)
      = Module.finrank ℝ W := T.toLinearEquiv.finrank_map_eq W
  have heq : W.map T.toLinearEquiv.toLinearMap = W :=
    Submodule.eq_of_le_of_finrank_eq hmap hfin
  intro w hw
  rw [← heq] at hw
  obtain ⟨y, hy, hTy⟩ := hw
  exact ⟨y, hy, hTy⟩

end Problems.Geometry.banach_tarski
