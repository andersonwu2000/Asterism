import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_endo_finrank_one_eq_smul_id

namespace Problems.Geometry.banach_tarski

-- In a 1-dim space every endomorphism is a scalar c • id (sub-goal
-- `endo_finrank_one_eq_smul_id`). Then det f = c^finrank · det id = c (finrank=1),
-- and (c•id) x = c • x, closing f x = (det f) • x.
theorem s11426
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (f : F →ₗ[ℝ] F) (hfin : Module.finrank ℝ F = 1) (x : F) :
    f x = (LinearMap.det f) • x  := by
  have h1 := endo_finrank_one_eq_smul_id f hfin
  obtain ⟨c, hc⟩ := h1
  rw [hc, LinearMap.det_smul, LinearMap.det_id, hfin, pow_one, mul_one]
  simp [LinearMap.smul_apply]

end Problems.Geometry.banach_tarski
