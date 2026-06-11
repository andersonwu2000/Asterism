import Mathlib
import Problems.Geometry.stokes_form_coord_cont.Defs

namespace Problems.Geometry.stokes_form_coord_cont

open scoped Manifold ContDiff

-- `formCoordChange I k i j` is definitionally `compContinuousLinearMapCLM ∘ coordChange j i`;
-- compose global continuity of `compContinuousLinearMapCLM` (in its CLM argument) with the
-- `continuousOn_coordChange` structure field, then flip the intersection with `inter_comm`.
theorem s11666 : ∀ {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H] (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    (k : ℕ) (i j : atlas H M),
    ContinuousOn (formCoordChange I k i j)
      ((tangentBundleCore I M).baseSet i ∩ (tangentBundleCore I M).baseSet j)  := by
  intro E _ _ H _ I M _ _ _ k i j
  rw [Set.inter_comm]
  exact ContinuousAlternatingMap.continuous_compContinuousLinearMapCLM.comp_continuousOn
    ((tangentBundleCore I M).continuousOn_coordChange j i)

end Problems.Geometry.stokes_form_coord_cont
