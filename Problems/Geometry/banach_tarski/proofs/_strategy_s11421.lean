import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_invariant_submodule_image_surj

namespace Problems.Geometry.banach_tarski

-- A linear isometry equiv preserving a finite-dim submodule W also preserves Wᗮ.
-- Single sub-goal: T maps W *onto* W (injective + equal finrank ⇒ surjective onto W).
-- Closer: x ∈ Wᗮ, w ∈ W; write w = T y with y ∈ W, then ⟪w, T x⟫ = ⟪T y, T x⟫ =
-- ⟪y, x⟫ = 0 by inner_map_map and x ∈ Wᗮ. The onto-W fact is the only real work.
theorem s11421
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (T : F ≃ₗᵢ[ℝ] F) (W : Submodule ℝ F)
    (hW : ∀ x ∈ W, T x ∈ W) :
    ∀ x ∈ Submodule.orthogonal W, T x ∈ Submodule.orthogonal W  := by
  have hsurj := invariant_submodule_image_surj T W hW
  intro x hx
  rw [Submodule.mem_orthogonal]
  intro w hw
  obtain ⟨y, hyW, rfl⟩ := hsurj w hw
  rw [T.inner_map_map]
  exact (Submodule.mem_orthogonal W x).mp hx y hyW

end Problems.Geometry.banach_tarski
