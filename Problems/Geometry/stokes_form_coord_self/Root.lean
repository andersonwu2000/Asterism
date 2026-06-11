import Mathlib
import Problems.Geometry.stokes_form_coord_self.Defs

open scoped Manifold Bundle ContDiff
open Bundle

namespace Problems.Geometry.stokes_form_coord_self

-- stokes_form_coord_self/main: self-transition of formCoordChange is the identity;
-- follows from VectorBundleCore.coordChange_self applied pointwise after ext.
theorem main : ∀ {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H] (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    (k : ℕ) (i : atlas H M),
    ∀ x ∈ (tangentBundleCore I M).baseSet i, ∀ v,
      formCoordChange I k i i x v = v := by
  intro E _ _ H _ I M _ _ _ k i x hx v
  simp only [formCoordChange, ContinuousAlternatingMap.compContinuousLinearMapCLM_apply]
  ext m
  simp only [ContinuousAlternatingMap.compContinuousLinearMap_apply]
  congr 1
  funext l
  exact (tangentBundleCore I M).coordChange_self i x hx (m l)

end Problems.Geometry.stokes_form_coord_self
