import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_endo_eq_det_smul_of_finrank_one

namespace Problems.Geometry.banach_tarski

-- Split on finrank: 0 ⇒ F subsingleton ⇒ x = 0, both sides 0 (handled inline);
-- 1 ⇒ f is the scalar det f (single hard leaf). Combined by Nat.eq_zero_or_pos.
theorem s11425
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (f : F →ₗ[ℝ] F) (hfin : Module.finrank ℝ F ≤ 1) (x : F) :
    f x = (LinearMap.det f) • x  := by
  rcases Nat.eq_zero_or_pos (Module.finrank ℝ F) with h0 | hpos
  · have hsub : Subsingleton F := Module.finrank_zero_iff.mp h0
    rw [Subsingleton.elim x 0, map_zero, smul_zero]
  · have h1 : Module.finrank ℝ F = 1 := le_antisymm hfin hpos
    exact endo_eq_det_smul_of_finrank_one f h1 x

end Problems.Geometry.banach_tarski
