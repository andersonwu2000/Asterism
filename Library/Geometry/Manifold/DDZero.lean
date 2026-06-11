import Library.Geometry.Manifold.DiffFormBundle
import Library.Geometry.Manifold.ExtDerivCoordLemmas
import Library.Geometry.Manifold.MExtDeriv
import Library.Geometry.Manifold.MExtDerivCoord
import Mathlib.Analysis.Normed.Group.Basic
import Mathlib.Analysis.Normed.Module.Basic
import Mathlib.Data.Set.Function
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.VectorBundle.Basic
import Mathlib.Geometry.Manifold.VectorBundle.SmoothSection
import Mathlib.Topology.Algebra.Module.Basic
import Mathlib.Topology.FiberBundle.Trivialization

/-!
# d² = 0 for the exterior derivative on smooth manifolds

This file establishes that the exterior derivative operator `mextDeriv` satisfies `d ∘ d = 0`,
i.e., applying the exterior derivative twice to any smooth differential form yields zero.

## Main definitions

- `mextDeriv`: the exterior derivative of a smooth `k`-form, producing a smooth `(k+1)`-form.

## Main statements

- `form_in_coord_mext_deriv_eq`: the coordinate expression for `mextDeriv` of a form coincides
  with the flat exterior derivative `extDerivWithin` on the chart target.
- `mextDeriv_mextDeriv_eq_zero`: for any smooth `k`-form `φ` on a smooth manifold,
  `mextDeriv I (mextDeriv I φ) = 0`.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.ExtDerivCoordLemmas
open Library.Geometry.Manifold.MExtDeriv
open Library.Geometry.Manifold.MExtDerivCoord
open scoped Manifold Bundle ContDiff Topology

namespace Library.Geometry.Manifold.DDZero

variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

/-- The exterior derivative of a smooth `k`-form as a smooth `(k+1)`-form. -/
noncomputable def mextDeriv {k : ℕ} (φ : DiffForm I M k) : DiffForm I M (k + 1) where
  toFun := mextDerivFun I φ
  contMDiff_toFun := contMDiff_mextDerivFun I φ

/-- In local coordinates centered at `x₀`, the exterior derivative `mextDeriv I φ` evaluated
on the chart target equals the flat exterior derivative `extDerivWithin` of the coordinate
form `formInCoord I φ x₀`. -/
theorem form_in_coord_mext_deriv_eq {k : ℕ} (φ : DiffForm I M k) (x₀ : M) :
    ∀ y ∈ (extChartAt I x₀).target,
      formInCoord I (mextDeriv I φ) x₀ y
        = extDerivWithin (formInCoord I φ x₀) (Set.range I) y := by
  intro y hy
  have hp_src : (extChartAt I x₀).symm y ∈ (extChartAt I x₀).source :=
    (extChartAt I x₀).map_target hy
  have hp : (extChartAt I x₀).symm y ∈ (chartAt H x₀).source := by
    simpa only [extChartAt_source] using hp_src
  have h_rinv : extChartAt I x₀ ((extChartAt I x₀).symm y) = y :=
    (extChartAt I x₀).right_inv hy
  have h_read := mext_deriv_triv_read I φ x₀ ((extChartAt I x₀).symm y) hp
  have h_lhs : formInCoord I (mextDeriv I φ) x₀ y
      = ((trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
          (formBundleCore (M := M) I (k + 1)).Fiber x₀)
          ⟨(extChartAt I x₀).symm y,
            mextDerivFun I φ ((extChartAt I x₀).symm y)⟩).2 := by
    simp only [formInCoord]
    rw [Trivialization.continuousLinearMapAt_apply_of_mem ℝ _ hp]
    rfl
  rw [h_lhs, h_read, h_rinv]

/-- **d² = 0**: applying `mextDeriv` twice to any smooth `k`-form yields the zero
`(k+2)`-form. -/
theorem mextDeriv_mextDeriv_eq_zero {k : ℕ} (φ : DiffForm I M k) :
    mextDeriv I (mextDeriv I φ) = 0 := by
  refine ContMDiffSection.ext fun x₀ => ?_
  have h_bridge := form_in_coord_mext_deriv_eq I φ x₀
  change mextDerivFun I (mextDeriv I φ) x₀ = 0
  rw [mextDerivFun, ext_deriv_within_congr_chart_target I x₀ _ _ h_bridge,
    ext_deriv_within_dd_zero_at_base I φ x₀]
  exact ContinuousLinearMap.map_zero _

end Library.Geometry.Manifold.DDZero
