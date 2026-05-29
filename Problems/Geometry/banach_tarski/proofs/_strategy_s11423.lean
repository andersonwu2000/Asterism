import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_endo_finrank_le_one_eq_det_smul

namespace Problems.Geometry.banach_tarski

-- Reduce the isometry/`= refl` packaging to one pure linear-algebra fact:
-- in finrank ≤ 1 every endomorphism `f` acts as `f x = (det f) • x`
-- (dim 0: both sides 0; dim 1: `f` is the scalar `det f`). Apply it to
-- `T`'s underlying linear map, plug `det = 1`, and `ext` closes `T = refl`.
-- The isometry structure is irrelevant to the core, hence dropped in the sub-goal.
theorem s11423
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (T : F ≃ₗᵢ[ℝ] F)
    (hfin : Module.finrank ℝ F ≤ 1)
    (hdet : LinearMap.det (T.toLinearEquiv.toLinearMap) = 1) :
    T = LinearIsometryEquiv.refl ℝ F  := by
  ext x
  have h_scalar := endo_finrank_le_one_eq_det_smul T.toLinearEquiv.toLinearMap hfin x
  rw [hdet, one_smul] at h_scalar
  simpa using h_scalar

end Problems.Geometry.banach_tarski
