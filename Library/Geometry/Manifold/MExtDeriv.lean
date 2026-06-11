import Library.Geometry.Manifold.DiffFormBundle   -- DiffForm, formBundleCore, instForm*
import Library.Geometry.Manifold.ExtDerivWithin
import Library.Geometry.Manifold.MExtDerivCoord
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.Calculus.FDeriv.Basic
import Mathlib.Analysis.Calculus.FDeriv.ContinuousAlternatingMap
import Mathlib.Analysis.Calculus.FDeriv.Symmetric
import Mathlib.Geometry.Manifold.ContMDiff.Atlas
import Mathlib.Geometry.Manifold.ContMDiff.Basic
import Mathlib.Geometry.Manifold.ContMDiff.NormedSpace
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.VectorBundle.Basic
import Mathlib.Topology.FiberBundle.Basic

/-!
# Exterior derivative as a smooth section

This file proves that the exterior derivative of a smooth differential form on a manifold
assembles into a smooth section of the corresponding differential form bundle.

## Main statements

- `ext_deriv_coord_change_transport`: the coordinate-change transport of the `x`-chart exterior
  derivative equals the exterior derivative expressed directly in the `x₀`-chart.
- `ext_deriv_fixed_chart_contMDiff_at`: the map `x ↦ extDerivWithin (formInCoord I φ x₀) …` is
  smooth at `x₀` for a fixed base point.
- `mext_deriv_triv_read`: the trivialization readout of `mextDerivFun` equals the fixed-chart
  exterior derivative.
- `contMDiff_mextDerivFun`: `mextDerivFun I φ` is a smooth section of the degree-`(k+1)`
  differential form bundle.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.ExtDerivWithin
open Library.Geometry.Manifold.FormCoordChange
open Library.Geometry.Manifold.MExtDerivCoord
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.MExtDeriv

variable {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

/-- The `formCoordChange` transport of the exterior derivative in the `x`-chart back to the
`x₀`-chart equals the exterior derivative of `formInCoord I φ x₀` at `extChartAt I x₀ x`.
This is the analytic heart of the smoothness proof: `formCoordChange` is precomposition by the
tangent transition derivative, and the identity follows from the pullback formula for exterior
derivatives together with chart-locality. -/
theorem ext_deriv_coord_change_transport
    {k : ℕ} (φ : DiffForm I M k) (x₀ x : M)
    (hx : x ∈ (chartAt H x₀).source) :
    formCoordChange I (k + 1) (achart H x) (achart H x₀) x
        (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x))
      = extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x) := by
  have hx' : x ∈ (extChartAt I x₀).source := by
    simpa only [extChartAt_source] using hx
  have hfy₀ : (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) (extChartAt I x₀ x)
      = extChartAt I x x :=
    congrArg (extChartAt I x) ((extChartAt I x₀).left_inv hx')
  have h_fcc : formCoordChange I (k + 1) (achart H x) (achart H x₀) x
      (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x))
    = (extDerivWithin (formInCoord I φ x) (Set.range I)
          (extChartAt I x x)).compContinuousLinearMap
        (fderivWithin ℝ (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) (Set.range I)
          (extChartAt I x₀ x)) := by
    simp only [formCoordChange, ContinuousAlternatingMap.compContinuousLinearMapCLM_apply,
      tangentBundleCore_coordChange_achart]
  have h_f : ContDiffWithinAt ℝ ∞ (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm)
      (Set.range I) (extChartAt I x₀ x) := by
    refine contDiffWithinAt_ext_coord_change x x₀ ?_
    rw [PartialEquiv.trans_source]
    refine ⟨(extChartAt I x₀).map_source hx', ?_⟩
    simp only [Set.mem_preimage, (extChartAt I x₀).left_inv hx']
    exact mem_extChartAt_source x
  have h_ω : DifferentiableWithinAt ℝ (formInCoord I φ x) (Set.range I) (extChartAt I x x) :=
    form_in_coord_differentiable_within_range I φ x
  have h_loc : extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x)
      = extDerivWithin
          (fun y => (formInCoord I φ x
              ((↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) y)).compContinuousLinearMap
            (fderivWithin ℝ (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) (Set.range I) y))
          (Set.range I) (extChartAt I x₀ x) :=
    ext_deriv_locality_pullback I φ x₀ x hx
  have h_pull : extDerivWithin
        (fun y => (formInCoord I φ x
            ((↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) y)).compContinuousLinearMap
          (fderivWithin ℝ (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) (Set.range I) y))
        (Set.range I) (extChartAt I x₀ x)
      = (extDerivWithin (formInCoord I φ x) (Set.range I)
            ((↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm)
              (extChartAt I x₀ x))).compContinuousLinearMap
          (fderivWithin ℝ (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) (Set.range I)
            (extChartAt I x₀ x)) := by
    apply extDerivWithin_pullback (r := ∞) (hfy₀ ▸ h_ω) h_f ?_ I.uniqueDiffOn ?_ ?_ ?_
    · simp only [minSmoothness_of_isRCLikeNormedField]
      exact ENat.LEInfty.out
    · exact I.range_subset_closure_interior (Set.mem_range_self _)
    · exact Set.mem_range_self _
    · intro y _
      exact ⟨chartAt H x ((extChartAt I x₀).symm y), rfl⟩
  rw [h_fcc, h_loc, h_pull, hfy₀]

/-- The map `x ↦ extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x)` is
smooth at `x₀`, for any fixed base chart point `x₀`. -/
theorem ext_deriv_fixed_chart_contMDiff_at
    {k : ℕ} (φ : DiffForm I M k) (x₀ : M) :
    ContMDiffAt I 𝓘(ℝ, E [⋀^Fin (k + 1)]→L[ℝ] ℝ) ∞
      (fun x => extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x))
      x₀ := by
  have h_form : ContDiffOn ℝ ∞ (formInCoord I φ x₀) (extChartAt I x₀).target :=
    form_in_coord_smooth I φ x₀
  have h_target : ContDiffOn ℝ ∞
      (extDerivWithin (formInCoord I φ x₀) (extChartAt I x₀).target)
      (extChartAt I x₀).target :=
    extDerivWithin_contDiffOn h_form (uniqueDiffOn_extChartAt_target x₀)
  have h_eqon : Set.EqOn (extDerivWithin (formInCoord I φ x₀) (Set.range I))
      (extDerivWithin (formInCoord I φ x₀) (extChartAt I x₀).target)
      (extChartAt I x₀).target := by
    intro y hy
    exact extDerivWithin_eq_of_mem_nhdsWithin
      (extChartAt_target_mem_nhdsWithin_of_mem hy)
      (I.uniqueDiffOn _ ((extChartAt_target_subset_range x₀) hy))
      ((h_form y hy).differentiableWithinAt (by simp))
  have h_range : ContDiffOn ℝ ∞
      (extDerivWithin (formInCoord I φ x₀) (Set.range I)) (extChartAt I x₀).target :=
    h_target.congr h_eqon
  have h_outer : ContMDiffOn 𝓘(ℝ, E) 𝓘(ℝ, E [⋀^Fin (k + 1)]→L[ℝ] ℝ) ∞
      (extDerivWithin (formInCoord I φ x₀) (Set.range I)) (extChartAt I x₀).target :=
    contMDiffOn_iff_contDiffOn.mpr h_range
  have h_chart : ContMDiffOn I 𝓘(ℝ, E) ∞ (extChartAt I x₀) (chartAt H x₀).source :=
    contMDiffOn_extChartAt
  have h_maps : Set.MapsTo (extChartAt I x₀) (chartAt H x₀).source (extChartAt I x₀).target := by
    intro x hx
    exact (extChartAt I x₀).map_source (by simpa [extChartAt_source] using hx)
  have h_comp : ContMDiffOn I 𝓘(ℝ, E [⋀^Fin (k + 1)]→L[ℝ] ℝ) ∞
      (fun x => extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x))
      (chartAt H x₀).source :=
    h_outer.comp h_chart h_maps
  exact h_comp.contMDiffAt
    ((chartAt H x₀).open_source.mem_nhds (mem_chart_source H x₀))

/-- The second component of the trivialization of `⟨x, mextDerivFun I φ x⟩` at basepoint `x₀`
equals the exterior derivative of `formInCoord I φ x₀` evaluated at `extChartAt I x₀ x`. -/
theorem mext_deriv_triv_read
    {k : ℕ} (φ : DiffForm I M k) (x₀ x : M)
    (hx : x ∈ (chartAt H x₀).source) :
    ((trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
        (formBundleCore (M := M) I (k + 1)).Fiber x₀) ⟨x, mextDerivFun I φ x⟩).2
      = extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x) := by
  have h_read := triv_read_mext_deriv_eq_coord_change I φ x₀ x
  have h_transport := ext_deriv_coord_change_transport I φ x₀ x hx
  exact h_read.trans h_transport

/-- `mextDerivFun I φ` is a smooth section of the degree-`(k+1)` differential form bundle
over `M`. -/
theorem contMDiff_mextDerivFun {k : ℕ} (φ : DiffForm I M k) :
    ContMDiff I (I.prod 𝓘(ℝ, E [⋀^Fin (k + 1)]→L[ℝ] ℝ)) ∞
      (fun x => Bundle.TotalSpace.mk'
        (E := fun y => (formBundleCore (M := M) I (k + 1)).Fiber y)
        (E [⋀^Fin (k + 1)]→L[ℝ] ℝ) x (mextDerivFun I φ x)) := by
  intro x₀
  have hx₀ : x₀ ∈ (trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
      (formBundleCore (M := M) I (k + 1)).Fiber x₀).baseSet :=
    FiberBundle.mem_baseSet_trivializationAt' x₀
  rw [Bundle.Trivialization.contMDiffAt_section_iff _ hx₀]
  have h_smooth : ContMDiffAt I 𝓘(ℝ, E [⋀^Fin (k + 1)]→L[ℝ] ℝ) ∞
      (fun x => extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x)) x₀ :=
    ext_deriv_fixed_chart_contMDiff_at I φ x₀
  refine h_smooth.congr_of_eventuallyEq ?_
  filter_upwards [(chartAt H x₀).open_source.mem_nhds (mem_chart_source H x₀)] with x hx
  exact mext_deriv_triv_read I φ x₀ x hx

end Library.Geometry.Manifold.MExtDeriv
