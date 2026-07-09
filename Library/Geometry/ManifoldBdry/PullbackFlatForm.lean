import Mathlib.AlgebraicTopology.SimplexCategory.Basic
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.Geometry.Manifold.Sheaf.Basic
import Mathlib.Order.BourbakiWitt
import Library.Geometry.Manifold.AlternatingMapContDiff   -- contdiff_comp_continuous_linear_map_clm
import Library.Geometry.Manifold.DiffFormBundle          -- DiffForm, formBundleCore, instForm*
import Library.Geometry.Manifold.MExtDerivCoord

/-!
# Pullback of flat differential forms on manifolds with boundary

This file constructs the fibrewise pullback of a smooth flat differential `k`-form along a
smooth map `e : N → F`, where `N` is a manifold with boundary modeled on
`EuclideanHalfSpace (n + 1)` and `F` is a normed space, and proves that the resulting
section of the form bundle is smooth.

## Main definitions

- `pullbackFlatFormFun`: the raw fibrewise pullback section; at `p` it precomposes `φ (e p)`
  by the `fderivWithin` of `e ∘ (extChartAt p).symm` and transports into the form-bundle
  fibre over `p`.

## Main statements

- `contMDiff_pullbackFlatFormFun`: the section `p ↦ pullbackFlatFormFun e φ p` into the
  total space of the form bundle is $C^\infty$.
-/

open Bundle
open Library.Geometry.Manifold.AlternatingMapContDiff
open Library.Geometry.Manifold.DiffFormBundle
open scoped Manifold Bundle ContDiff
open scoped Manifold ContDiff

namespace Library.Geometry.ManifoldBdry.PullbackFlatForm

variable {n k : ℕ}
  {N : Type*} [TopologicalSpace N]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
  {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]

/-- Raw fibrewise section of `e* φ`: at `p`, precompose `φ (e p)` (an alternating
`k`-form on `F`) by the coordinate derivative of `e` at `p`, then transport into the
form-bundle fibre over `p`. -/
noncomputable def pullbackFlatFormFun (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (p : N) : (formBundleCore (𝓡∂ (n + 1)) (M := N) k).Fiber p :=
  Trivialization.symmL ℝ
    (trivializationAt (EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ)
      (formBundleCore (𝓡∂ (n + 1)) (M := N) k).Fiber p) p
    ((φ (e p)).compContinuousLinearMap
      (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p).symm)
        (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p p)))

/-- The composition `φ ∘ e ∘ (extChartAt p0).symm` is $C^\infty$ on the chart target.
Extracts `ContDiffOn` from `he` via `contMDiff_iff` (the flat model collapses to identity),
then prepends `hφ` via `ContDiff.comp_contDiffOn`. -/
theorem pullback_flat_form_comp_contdiffon
    {n k : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hφ : ContDiff ℝ ∞ φ) (p0 : N) :
    ContDiffOn ℝ ∞
      (fun y => φ (e ((extChartAt (𝓡∂ (n + 1)) p0).symm y)))
      (extChartAt (𝓡∂ (n + 1)) p0).target := by
  apply hφ.comp_contDiffOn
  have h_cd := ((contMDiff_iff (I := 𝓡∂ (n + 1)) (I' := 𝓘(ℝ, F))).mp he).2 p0 (e p0)
  simp only [extChartAt_model_space_eq_id, PartialEquiv.refl_source,
    Set.preimage_univ, Set.inter_univ] at h_cd
  exact h_cd

/-- The map `e ∘ (extChartAt p0).symm` is $C^\infty$ on the chart target.
Extracted from `ContMDiff e` via `contMDiff_iff`; the flat target model collapses the
chart to the identity. -/
theorem pullback_flat_chart_read_contdiffon
    {n : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (p0 : N) :
    ContDiffOn ℝ ∞ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
      (extChartAt (𝓡∂ (n + 1)) p0).target := by
  have h := ((contMDiff_iff (I := 𝓡∂ (n + 1)) (I' := 𝓘(ℝ, F))).mp he).2 p0 (e p0)
  simp only [extChartAt_model_space_eq_id, PartialEquiv.refl_coe,
    PartialEquiv.refl_source, Set.preimage_univ, Set.inter_univ] at h
  exact h

/-- At a point `y` in the chart target, `fderivWithin` of `e ∘ (extChartAt p0).symm`
within `range 𝓡∂` equals `fderivWithin` within the chart target itself, via
`fderivWithin_congr_set` applied to `extChartAt_target_eventuallyEq_of_mem`. -/
theorem fderiv_within_range_eq_chart_target
    {n : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (_he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (p0 : N)
    (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hy : y ∈ (extChartAt (𝓡∂ (n + 1)) p0).target) :
    fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm) (Set.range (𝓡∂ (n + 1))) y
      = fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
          (extChartAt (𝓡∂ (n + 1)) p0).target y :=
      fderivWithin_congr_set (extChartAt_target_eventuallyEq_of_mem hy).symm

/-- The function `y ↦ fderivWithin ℝ (e ∘ (extChartAt p0).symm) (range 𝓡∂) y` is
$C^\infty$ on the chart target. Uses `pullback_flat_chart_read_contdiffon` and
`ContDiffOn.fderivWithin`, then `congr`s using `fderiv_within_range_eq_chart_target`. -/
theorem pullback_flat_fderiv_within_chart_contdiffon
    {n : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (p0 : N) :
    ContDiffOn ℝ ∞
      (fun y => fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
        (Set.range (𝓡∂ (n + 1))) y)
      (extChartAt (𝓡∂ (n + 1)) p0).target  := by
  have h_read := pullback_flat_chart_read_contdiffon e he p0
  have h_target : ContDiffOn ℝ ∞
      (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
        (extChartAt (𝓡∂ (n + 1)) p0).target)
      (extChartAt (𝓡∂ (n + 1)) p0).target :=
    h_read.fderivWithin (uniqueDiffOn_extChartAt_target p0) (by simp)
  apply h_target.congr
  intro y hy
  exact fderiv_within_range_eq_chart_target e he p0 y hy

/-- The coordinate representative
`y ↦ (φ (e (chart.symm y))).compContinuousLinearMap (fderivWithin (e ∘ chart.symm) (range I) y)`
is $C^\infty$ on the chart target. Combines `pullback_flat_form_comp_contdiffon` (smoothness
of `φ ∘ e ∘ chart.symm`) and `pullback_flat_fderiv_within_chart_contdiffon` (smoothness of
the derivative map) via `contdiff_comp_continuous_linear_map_clm` and `ContDiffOn.clm_apply`. -/
theorem pullback_flat_coord_rep_within_contdiffon
    {n k : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hφ : ContDiff ℝ ∞ φ) (p0 : N) :
    ContDiffOn ℝ ∞
      (fun y => (φ (e ((extChartAt (𝓡∂ (n + 1)) p0).symm y))).compContinuousLinearMap
          (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
            (Set.range (𝓡∂ (n + 1))) y))
      (extChartAt (𝓡∂ (n + 1)) p0).target  := by
  have hB : ContDiffOn ℝ ∞ (fun y => φ (e ((extChartAt (𝓡∂ (n + 1)) p0).symm y)))
      (extChartAt (𝓡∂ (n + 1)) p0).target :=
    pullback_flat_form_comp_contdiffon e φ he hφ p0
  have hA1 : ContDiffOn ℝ ∞
      (fun y => fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
        (Set.range (𝓡∂ (n + 1))) y)
      (extChartAt (𝓡∂ (n + 1)) p0).target :=
    pullback_flat_fderiv_within_chart_contdiffon e he p0
  have hA : ContDiffOn ℝ ∞
      (fun y => ContinuousAlternatingMap.compContinuousLinearMapCLM (ι := Fin k) (F := ℝ)
        (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
          (Set.range (𝓡∂ (n + 1))) y))
      (extChartAt (𝓡∂ (n + 1)) p0).target := by
    have hclm := contdiff_comp_continuous_linear_map_clm
      (E := EuclideanSpace ℝ (Fin (n + 1))) (F := F) (G := ℝ) (ι := Fin k) (n := (∞ : ℕ∞ω))
    exact hclm.comp_contDiffOn hA1
  simp only [← ContinuousAlternatingMap.compContinuousLinearMapCLM_apply]
  exact hA.clm_apply hB

/-- Smooth differentiability at `p0` of the fixed-chart coordinate representative.
Factors `fun p => g (extChartAt p0 p)` as `g ∘ extChartAt p0` and applies
`ContMDiffOn.comp` followed by `.contMDiffAt` at the source neighborhood of `p0`.
Here `h_outer` (smoothness of `g` on the chart target) comes from
`pullback_flat_coord_rep_within_contdiffon`, and `h_inner` (smoothness of `extChartAt p0`)
from `contMDiffOn_extChartAt`. -/
theorem pullback_flat_fixed_chart_contmdiff_at
    {n k : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hφ : ContDiff ℝ ∞ φ) (p0 : N) :
    ContMDiffAt (𝓡∂ (n + 1))
      𝓘(ℝ, EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ) ∞
      (fun p : N =>
        (φ (e ((extChartAt (𝓡∂ (n + 1)) p0).symm
                (extChartAt (𝓡∂ (n + 1)) p0 p)))).compContinuousLinearMap
          (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
            (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p0 p))) p0  := by
  have h_outer : ContMDiffOn 𝓘(ℝ, EuclideanSpace ℝ (Fin (n + 1)))
      𝓘(ℝ, EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ) ∞
      (fun y => (φ (e ((extChartAt (𝓡∂ (n + 1)) p0).symm y))).compContinuousLinearMap
          (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
            (Set.range (𝓡∂ (n + 1))) y))
      (extChartAt (𝓡∂ (n + 1)) p0).target :=
    contMDiffOn_iff_contDiffOn.mpr
      (pullback_flat_coord_rep_within_contdiffon e φ he hφ p0)
  have h_inner : ContMDiffOn (𝓡∂ (n + 1)) 𝓘(ℝ, EuclideanSpace ℝ (Fin (n + 1))) ∞
      (fun p : N => extChartAt (𝓡∂ (n + 1)) p0 p) (extChartAt (𝓡∂ (n + 1)) p0).source :=
    contMDiffOn_extChartAt.mono (extChartAt_source (𝓡∂ (n + 1)) p0).le
  have h_maps : Set.MapsTo (fun p : N => extChartAt (𝓡∂ (n + 1)) p0 p)
      (extChartAt (𝓡∂ (n + 1)) p0).source (extChartAt (𝓡∂ (n + 1)) p0).target :=
    (extChartAt (𝓡∂ (n + 1)) p0).mapsTo
  have h_nhds : (extChartAt (𝓡∂ (n + 1)) p0).source ∈ nhds p0 :=
    extChartAt_source_mem_nhds p0
  exact (h_outer.comp h_inner h_maps).contMDiffAt h_nhds

/-- The trivialization read of `pullbackFlatFormFun e φ p` through the trivialization at `p0`
collapses to `formCoordChange (achart p) (achart p0) p` of the local coordinate value.
Unfolds `pullbackFlatFormFun` (a `symmL` build), rewrites `symmL` as
`coordChange (indexAt p) (indexAt p)` via `trivializationAt_symmL`, reads through the
trivialization at `p0` definitionally by `rfl`, then cancels the self-transition with
`coordChange_self`. -/
theorem flat_triv_read_coord_change
    {n k : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (p0 p : N) :
    ((trivializationAt (EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ)
        (formBundleCore (𝓡∂ (n + 1)) (M := N) k).Fiber p0)
        ⟨p, pullbackFlatFormFun e φ p⟩).2
      = Library.Geometry.Manifold.FormCoordChange.formCoordChange (𝓡∂ (n + 1)) k
          (achart (EuclideanHalfSpace (n + 1)) p)
          (achart (EuclideanHalfSpace (n + 1)) p0) p
          ((φ (e p)).compContinuousLinearMap
            (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p).symm)
              (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p p)))  := by
  simp only [pullbackFlatFormFun]
  have hmem : p ∈ (trivializationAt (EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ)
      (formBundleCore (𝓡∂ (n + 1)) (M := N) k).Fiber p).baseSet :=
    (formBundleCore (𝓡∂ (n + 1)) (M := N) k).mem_localTrivAt_baseSet p
  have hfun : (trivializationAt (EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ)
      (formBundleCore (𝓡∂ (n + 1)) (M := N) k).Fiber p).symmL ℝ p =
      (formBundleCore (𝓡∂ (n + 1)) (M := N) k).coordChange
        ((formBundleCore (𝓡∂ (n + 1)) (M := N) k).indexAt p)
        ((formBundleCore (𝓡∂ (n + 1)) (M := N) k).indexAt p) p :=
    (formBundleCore (𝓡∂ (n + 1)) (M := N) k).trivializationAt_symmL hmem
  rw [hfun]
  have step1 : ∀ (z : (formBundleCore (𝓡∂ (n + 1)) (M := N) k).Fiber p),
      ((trivializationAt (EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ)
          (formBundleCore (𝓡∂ (n + 1)) (M := N) k).Fiber p0) ⟨p, z⟩).2 =
        Library.Geometry.Manifold.FormCoordChange.formCoordChange (𝓡∂ (n + 1)) k
          (achart (EuclideanHalfSpace (n + 1)) p)
          (achart (EuclideanHalfSpace (n + 1)) p0) p z :=
    fun _ ↦ rfl
  rw [step1]
  have hself := (formBundleCore (𝓡∂ (n + 1)) (M := N) k).coordChange_self
    ((formBundleCore (𝓡∂ (n + 1)) (M := N) k).indexAt p) p
    ((formBundleCore (𝓡∂ (n + 1)) (M := N) k).mem_baseSet_at p)
    ((φ (e p)).compContinuousLinearMap
      (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p).symm)
        (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p p)))
  exact congrArg
    (Library.Geometry.Manifold.FormCoordChange.formCoordChange (𝓡∂ (n + 1)) k
      (achart (EuclideanHalfSpace (n + 1)) p) (achart (EuclideanHalfSpace (n + 1)) p0) p)
    hself

/-- Differentiable case of the chart-change chain rule for the coordinate-read derivative.
The tangent transition `coordChange (achart p0) (achart p) p = tangentCoordChange I p0 p p`
has chart-transition derivative `hasFDerivWithinAt_tangentCoordChange`; composing it with
`hd.hasFDerivWithinAt` via `HasFDerivWithinAt.comp`, then transporting along the
chart-overlap identity `e ∘ chart_p0.symm =ᶠ (e ∘ chart_p.symm) ∘ (chart_p ∘ chart_p0.symm)`
near `chart_p0 p` within `range I`, gives a `HasFDerivWithinAt` for `e ∘ chart_p0.symm`;
`.fderivWithin` with `range I` unique differentiability closes the goal. -/
theorem flat_coord_chain_diff_case
    {n : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (p0 p : N)
    (hp : p ∈ (chartAt (EuclideanHalfSpace (n + 1)) p0).source)
    (hd : DifferentiableWithinAt ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p).symm)
        (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p p)) :
    (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p).symm)
        (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p p)).comp
      ((tangentBundleCore (𝓡∂ (n + 1)) N).coordChange
        (achart (EuclideanHalfSpace (n + 1)) p0)
        (achart (EuclideanHalfSpace (n + 1)) p) p)
    = fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
        (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p0 p)  := by
  set I := 𝓡∂ (n + 1) with hI
  have hsrc_p0 : p ∈ (extChartAt I p0).source := by
    rw [extChartAt_source]; exact hp
  have hsrc_p : p ∈ (extChartAt I p).source := mem_extChartAt_source p
  have hT : HasFDerivWithinAt (extChartAt I p ∘ (extChartAt I p0).symm)
      (tangentCoordChange I p0 p p) (Set.range I) (extChartAt I p0 p) :=
    hasFDerivWithinAt_tangentCoordChange ⟨hsrc_p0, hsrc_p⟩
  have hbase : (extChartAt I p ∘ (extChartAt I p0).symm) (extChartAt I p0 p)
      = extChartAt I p p := by
    simp only [Function.comp_apply, PartialEquiv.left_inv _ hsrc_p0]
  have hE : HasFDerivWithinAt (e ∘ (extChartAt I p).symm)
      (fderivWithin ℝ (e ∘ (extChartAt I p).symm) (Set.range I) (extChartAt I p p))
      (Set.range I) ((extChartAt I p ∘ (extChartAt I p0).symm) (extChartAt I p0 p)) := by
    rw [hbase]; exact hd.hasFDerivWithinAt
  have hmaps : Set.MapsTo (extChartAt I p ∘ (extChartAt I p0).symm)
      (Set.range I) (Set.range I) := by
    intro x _hx
    exact ⟨_, rfl⟩
  have hcomp := hE.comp (extChartAt I p0 p) hT hmaps
  have h_overlap : (e ∘ (extChartAt I p0).symm)
      =ᶠ[nhdsWithin (extChartAt I p0 p) (Set.range I)]
      ((e ∘ (extChartAt I p).symm) ∘ (extChartAt I p ∘ (extChartAt I p0).symm)) := by
    have hmem : (extChartAt I p0).symm ⁻¹' (extChartAt I p).source
        ∈ nhds (extChartAt I p0 p) :=
      extChartAt_preimage_mem_nhds' hsrc_p0 (extChartAt_source_mem_nhds p)
    refine Filter.eventuallyEq_of_mem (mem_nhdsWithin_of_mem_nhds hmem) ?_
    intro y hy
    simp only [Set.mem_preimage] at hy
    simp only [Function.comp_apply]
    rw [PartialEquiv.left_inv _ hy]
  have hpt : (e ∘ (extChartAt I p0).symm) (extChartAt I p0 p)
      = ((e ∘ (extChartAt I p).symm) ∘ (extChartAt I p ∘ (extChartAt I p0).symm))
        (extChartAt I p0 p) := by
    simp only [Function.comp_apply, PartialEquiv.left_inv _ hsrc_p0,
      PartialEquiv.left_inv _ hsrc_p]
  have hcong := hcomp.congr_of_eventuallyEq h_overlap hpt
  have hfd := hcong.fderivWithin (I.uniqueDiffOn.uniqueDiffWithinAt (Set.mem_range_self _))
  exact hfd.symm

/-- Transfers differentiability of `e ∘ chart_p0.symm` from basepoint `p0` to basepoint `p`
(with `p` in `p0`'s chart source) by precomposing with the smooth chart transition
`tangentCoordChange p p0 p`. `hasFDerivWithinAt_tangentCoordChange` gives the transition a
derivative at `extChartAt p p`; `hd` composes with it via `DifferentiableWithinAt.comp`
(MapsTo holds since `extChartAt p0 _ ∈ range I`), and the identity
`(e ∘ chart_p0.symm) ∘ transition =ᶠ e ∘ chart_p.symm` near `extChartAt p p` within
`range I` closes by `congr_of_eventuallyEq`. -/
theorem flat_coord_diff_transfer
    {n : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (p0 p : N)
    (hp : p ∈ (chartAt (EuclideanHalfSpace (n + 1)) p0).source)
    (hd : DifferentiableWithinAt ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
        (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p0 p)) :
    DifferentiableWithinAt ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p).symm)
        (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p p)  := by
  have hp0src : p ∈ (extChartAt (𝓡∂ (n + 1)) p0).source := by
    rw [extChartAt_source]; exact hp
  have hmem : p ∈ (extChartAt (𝓡∂ (n + 1)) p).source ∩ (extChartAt (𝓡∂ (n + 1)) p0).source :=
    ⟨mem_extChartAt_source p, hp0src⟩
  have hT := hasFDerivWithinAt_tangentCoordChange
    (I := 𝓡∂ (n + 1)) (x := p) (y := p0) (z := p) hmem
  have hTd := hT.differentiableWithinAt
  have hpt : (⇑(extChartAt (𝓡∂ (n + 1)) p0) ∘ ⇑(extChartAt (𝓡∂ (n + 1)) p).symm)
      (extChartAt (𝓡∂ (n + 1)) p p) = extChartAt (𝓡∂ (n + 1)) p0 p := by
    simp only [Function.comp_apply, extChartAt_to_inv]
  have hg : DifferentiableWithinAt ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
      (Set.range (𝓡∂ (n + 1)))
      ((⇑(extChartAt (𝓡∂ (n + 1)) p0) ∘ ⇑(extChartAt (𝓡∂ (n + 1)) p).symm)
        (extChartAt (𝓡∂ (n + 1)) p p)) := by
    rw [hpt]; exact hd
  have hmaps : Set.MapsTo
      (⇑(extChartAt (𝓡∂ (n + 1)) p0) ∘ ⇑(extChartAt (𝓡∂ (n + 1)) p).symm)
      (Set.range (𝓡∂ (n + 1))) (Set.range (𝓡∂ (n + 1))) := by
    intro y _
    simp only [Function.comp_apply, extChartAt_coe]
    exact Set.mem_range_self _
  have hcomp := hg.comp (extChartAt (𝓡∂ (n + 1)) p p) hTd hmaps
  have hsrc : (extChartAt (𝓡∂ (n + 1)) p0).source ∈ nhds p :=
    extChartAt_source_mem_nhds' hp0src
  have hUnhds : (extChartAt (𝓡∂ (n + 1)) p).symm ⁻¹' (extChartAt (𝓡∂ (n + 1)) p0).source
      ∈ nhdsWithin (extChartAt (𝓡∂ (n + 1)) p p) (Set.range (𝓡∂ (n + 1))) := by
    rw [← map_extChartAt_symm_nhdsWithin_range (I := 𝓡∂ (n + 1)) p, Filter.mem_map] at hsrc
    exact hsrc
  refine hcomp.congr_of_eventuallyEq ?_ ?_
  · filter_upwards [hUnhds] with y hy
    simp only [Function.comp_apply]
    rw [(extChartAt (𝓡∂ (n + 1)) p0).left_inv hy]
  · simp only [Function.comp_apply, extChartAt_to_inv]
    rw [(extChartAt (𝓡∂ (n + 1)) p0).left_inv hp0src]

/-- Chart-change chain rule for the coordinate-read derivative, without assuming `e` smooth.
Case-splits on differentiability of `e ∘ chart_p.symm` at `chart_p p`:
- Differentiable case: `flat_coord_chain_diff_case` gives the standard chain rule.
- Non-differentiable case: both sides are zero — `fderivWithin (e ∘ chart_p.symm)` is junk
  `0`, and `flat_coord_diff_transfer` (contrapositive) shows `e ∘ chart_p0.symm` is also
  non-differentiable, so its `fderivWithin` is `0`; closed by `zero_comp`. -/
theorem fderivWithin_comp_coordChange_eq
    {n : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F)
    (p0 p : N)
    (hp : p ∈ (chartAt (EuclideanHalfSpace (n + 1)) p0).source) :
    (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p).symm)
        (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p p)).comp
      ((tangentBundleCore (𝓡∂ (n + 1)) N).coordChange
        (achart (EuclideanHalfSpace (n + 1)) p0)
        (achart (EuclideanHalfSpace (n + 1)) p) p)
    = fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
        (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p0 p)  := by
  by_cases hd : DifferentiableWithinAt ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p).symm)
        (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p p)
  · exact flat_coord_chain_diff_case e p0 p hp hd
  · rw [fderivWithin_zero_of_not_differentiableWithinAt hd,
        fderivWithin_zero_of_not_differentiableWithinAt
          (fun h => hd (flat_coord_diff_transfer e p0 p hp h)),
        ContinuousLinearMap.zero_comp]

/-- The trivialization read of `pullbackFlatFormFun e φ p` through the trivialization at `p0`
equals the fixed-basepoint pullback formula. Step 1: `flat_triv_read_coord_change` collapses
the read to `formCoordChange (achart p) (achart p0) p` of the local coordinate value.
Step 2: the basepoint is moved `p → p0` by unfolding `formCoordChange` and applying
`fderivWithin_comp_coordChange_eq` (the chart-read derivative chain rule). -/
theorem pullback_flat_triv_read
    {n k : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (p0 p : N)
    (hp : p ∈ (chartAt (EuclideanHalfSpace (n + 1)) p0).source) :
    ((trivializationAt (EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ)
        (formBundleCore (𝓡∂ (n + 1)) (M := N) k).Fiber p0)
        ⟨p, pullbackFlatFormFun e φ p⟩).2
      = (φ (e ((extChartAt (𝓡∂ (n + 1)) p0).symm
              (extChartAt (𝓡∂ (n + 1)) p0 p)))).compContinuousLinearMap
          (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p0).symm)
            (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p0 p))  := by
  rw [flat_triv_read_coord_change (n := n) (k := k) e φ p0 p]
  have hpt : (extChartAt (𝓡∂ (n + 1)) p0).symm (extChartAt (𝓡∂ (n + 1)) p0 p) = p :=
    (extChartAt (𝓡∂ (n + 1)) p0).left_inv (by rw [extChartAt_source]; exact hp)
  have h_chain := fderivWithin_comp_coordChange_eq e p0 p hp
  rw [hpt]
  simp only [Library.Geometry.Manifold.FormCoordChange.formCoordChange,
    ContinuousAlternatingMap.compContinuousLinearMapCLM_apply]
  ext m
  simp only [ContinuousAlternatingMap.compContinuousLinearMap_apply]
  rw [← h_chain]
  rfl

/-- **Smooth pullback section**: the section `p ↦ pullbackFlatFormFun e φ p` into the total
space of the form bundle is $C^\infty$. At each `p0` the section is read through the
trivialization at `p0` via `contMDiffAt_section_iff`, and `congr_of_eventuallyEq` reduces
the trivialization read (on the chart source) to the fixed-basepoint coordinate formula proved
in `pullback_flat_fixed_chart_contmdiff_at`. The coord-change naturality is
`pullback_flat_triv_read`. -/
theorem contMDiff_pullbackFlatFormFun : ∀ {n k : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ)),
    ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e → ContDiff ℝ ∞ φ →
    ContMDiff (𝓡∂ (n + 1))
        ((𝓡∂ (n + 1)).prod 𝓘(ℝ, EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ)) ∞
      (fun p => Bundle.TotalSpace.mk'
        (E := fun q => (formBundleCore (𝓡∂ (n + 1)) (M := N) k).Fiber q)
        (EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ) p
        (pullbackFlatFormFun e φ p))  := by
  intro n k N _ _ _ F _ _ e φ he hφ p0
  have hp0 : p0 ∈ (trivializationAt (EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ)
      (formBundleCore (𝓡∂ (n + 1)) (M := N) k).Fiber p0).baseSet :=
    FiberBundle.mem_baseSet_trivializationAt' p0
  rw [Bundle.Trivialization.contMDiffAt_section_iff _ hp0]
  have h_fixed := pullback_flat_fixed_chart_contmdiff_at e φ he hφ p0
  refine h_fixed.congr_of_eventuallyEq ?_
  filter_upwards [(chartAt (EuclideanHalfSpace (n + 1)) p0).open_source.mem_nhds
    (mem_chart_source (EuclideanHalfSpace (n + 1)) p0)] with p hp
  exact pullback_flat_triv_read e φ p0 p hp

end Library.Geometry.ManifoldBdry.PullbackFlatForm
