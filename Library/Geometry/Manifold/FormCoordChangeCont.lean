import Library.Geometry.Manifold.FormCoordChange
import Mathlib.Analysis.Normed.Group.Basic
import Mathlib.Analysis.Normed.Module.Alternating.Basic
import Mathlib.Analysis.Normed.Module.Basic
import Mathlib.Data.Set.Basic
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.VectorBundle.Tangent
import Mathlib.Topology.Basic
import Mathlib.Topology.ContinuousOn

/-!
# Continuity of the differential-form coordinate change map

This file establishes that the coordinate change map for differential `k`-forms,
`formCoordChange I k i j`, is continuous on the intersection of the base sets of
charts `i` and `j` in the tangent bundle core.

## Main statements

- `continuousOn_formCoordChange`: `formCoordChange I k i j` is continuous on
  `(tangentBundleCore I M).baseSet i ∩ (tangentBundleCore I M).baseSet j`.
-/

open Library.Geometry.Manifold.FormCoordChange
open scoped Manifold ContDiff

namespace Library.Geometry.Manifold.FormCoordChangeCont

/-- The coordinate change map for differential `k`-forms is continuous on the overlap of the
base sets of charts `i` and `j`. This follows by composing the global continuity of
`compContinuousLinearMapCLM` (in its linear map argument) with the `continuousOn_coordChange`
field of the tangent bundle core. -/
theorem continuousOn_formCoordChange {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H] (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    (k : ℕ) (i j : atlas H M) :
    ContinuousOn (formCoordChange I k i j)
      ((tangentBundleCore I M).baseSet i ∩ (tangentBundleCore I M).baseSet j) := by
  rw [Set.inter_comm]
  exact ContinuousAlternatingMap.continuous_compContinuousLinearMapCLM.comp_continuousOn
    ((tangentBundleCore I M).continuousOn_coordChange j i)

end Library.Geometry.Manifold.FormCoordChangeCont
