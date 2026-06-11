import Library.Geometry.Manifold.DiffFormBundle    -- DiffForm, formBundleCore, instForm*
import Library.Geometry.Manifold.MExtDeriv          -- contMDiff_mextDerivFun (smoothness)
import Library.Geometry.Manifold.MExtDerivCoord     -- mextDerivFun, formInCoord
import Mathlib.Analysis.Calculus.DifferentialForm.Basic
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt

/-!
# Exterior derivative coordinate lemmas

Two supporting lemmas for proving `d ∘ d = 0` on a smooth manifold, stated in
the model-space picture using `extDerivWithin` restricted to `Set.range I`.

## Main statements

- `ext_deriv_within_congr_chart_target`: congruence for `extDerivWithin` at a
  chart base point, promoting equality on `(extChartAt I x₀).target` to a
  `nhdsWithin` filter equality via `extChartAt_target_mem_nhdsWithin`.
- `ext_deriv_within_dd_zero_at_base`: `d(dφ) = 0` in model coordinates at a
  base point, via `extDerivWithin_extDerivWithin_apply`.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDeriv
open Library.Geometry.Manifold.MExtDerivCoord
open scoped Manifold Bundle ContDiff Topology

namespace Library.Geometry.Manifold.ExtDerivCoordLemmas

variable {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
variable {H : Type*} [TopologicalSpace H]
variable (I : ModelWithCorners ℝ E H)
variable {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

/-- Congruence for `extDerivWithin` restricted to `Set.range I` at a chart base point.
If `f` and `g` agree on `(extChartAt I x₀).target`, then their exterior derivatives
within `Set.range I` agree at `extChartAt I x₀ x₀`. -/
theorem ext_deriv_within_congr_chart_target
    (x₀ : M) {m : ℕ} (f g : E → (E [⋀^Fin m]→L[ℝ] ℝ))
    (h : ∀ y ∈ (extChartAt I x₀).target, f y = g y) :
    extDerivWithin f (Set.range I) (extChartAt I x₀ x₀)
      = extDerivWithin g (Set.range I) (extChartAt I x₀ x₀) := by
  apply Filter.EventuallyEq.extDerivWithin_eq _ (h _ (mem_extChartAt_target x₀))
  apply Filter.eventually_of_mem (extChartAt_target_mem_nhdsWithin x₀)
  exact h

/-- The exterior derivative satisfies `d(dφ) = 0` in model coordinates at a base point.
Applying `extDerivWithin · (Set.range I)` twice to `formInCoord I φ x₀` and evaluating
at `extChartAt I x₀ x₀` yields zero. -/
theorem ext_deriv_within_dd_zero_at_base
    {k : ℕ} (φ : DiffForm I M k) (x₀ : M) :
    extDerivWithin (extDerivWithin (formInCoord I φ x₀) (Set.range I))
      (Set.range I) (extChartAt I x₀ x₀) = 0 := by
  apply extDerivWithin_extDerivWithin_apply
  · exact ((form_in_coord_smooth I φ x₀).contDiffWithinAt
      (mem_extChartAt_target x₀)).mono_of_mem_nhdsWithin
      (extChartAt_target_mem_nhdsWithin x₀)
  · norm_num [minSmoothness]; exact WithTop.coe_le_coe.mpr le_top
  · exact I.uniqueDiffOn
  · exact I.range_subset_closure_interior
      (extChartAt_target_subset_range x₀ (mem_extChartAt_target x₀))
  · exact extChartAt_target_subset_range x₀ (mem_extChartAt_target x₀)

end Library.Geometry.Manifold.ExtDerivCoordLemmas
