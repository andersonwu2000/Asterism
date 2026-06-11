import Library.Geometry.Manifold.FormCoordChange
import Mathlib.Geometry.Manifold.VectorBundle.Tangent
import Mathlib.Topology.Algebra.Module.Alternating.Basic

/-!
# Self-transition of coordinate change for differential forms

This file shows that the coordinate change map `formCoordChange I k i i` is the identity
when the source and target charts coincide.

## Main statements

- `formCoordChange_self`: the self-transition `formCoordChange I k i i x v = v` holds for all
  `x` in the base set of chart `i` and all `v`.
-/

open Bundle
open Library.Geometry.Manifold.FormCoordChange
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.FormCoordChangeSelf

/-- The self-transition of `formCoordChange` is the identity: applying the coordinate change
from chart `i` to itself at any point `x` in the chart's base set returns the original
alternating map unchanged. -/
theorem formCoordChange_self {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H] (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    (k : ℕ) (i : atlas H M) :
    ∀ x ∈ (tangentBundleCore I M).baseSet i, ∀ v,
      formCoordChange I k i i x v = v := by
  intro x hx v
  simp only [formCoordChange, ContinuousAlternatingMap.compContinuousLinearMapCLM_apply]
  ext m
  simp only [ContinuousAlternatingMap.compContinuousLinearMap_apply]
  congr 1
  funext l
  exact (tangentBundleCore I M).coordChange_self i x hx (m l)

end Library.Geometry.Manifold.FormCoordChangeSelf
