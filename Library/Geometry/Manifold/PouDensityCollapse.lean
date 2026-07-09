import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.InducedOrientNonzero         -- inducedOrient, inducedOrient_ne_zero
import Library.Geometry.Manifold.IntegralEquivFinsum
import Library.Geometry.Manifold.LocalCoeffDensity
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBdry.PullbackBdryDefs         -- pullbackBdryFun
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff    -- contMDiff_pullbackBdryFun
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry
import Mathlib.Algebra.BigOperators.Finprod
import Mathlib.Algebra.Group.Support
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Data.Real.Sign
import Mathlib.Geometry.Manifold.BumpFunction
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.ContMDiff.Basic
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.PartitionOfUnity
import Mathlib.Logic.Equiv.PartialEquiv
import Mathlib.MeasureTheory.Integral.IntegrableOn
import Mathlib.MeasureTheory.MeasurableSpace.Basic
import Mathlib.MeasureTheory.Measure.MeasureSpace
import Mathlib.Topology.Algebra.Support
import Mathlib.Topology.Compactness.Compact
import Mathlib.Topology.Compactness.LocallyFinite
import Mathlib.Topology.ContinuousOn
import Mathlib.Topology.Separation.Hausdorff

/-!
# Partition-of-unity density collapse

This file proves that a PoU-weighted sum of oriented local densities collapses to the
single-chart density at any fixed chart center `c₀`, under the assumption that the
integrand form `g` is supported in `(chartAt EH c₀).source`.

## Main results

- `weighted_core_continuous_on_target`: the bump-weighted local coefficient is continuous on
  the chart target.
- `weighted_core_support_subset_compact`: its support sits inside a compact subset of the target.
- `weighted_core_integrable_generic`: the bump-weighted density core is integrable on the target.
- `weighted_signed_integrand_integrable`: the full signed single-bump integrand is integrable.
- `pou_density_core_integrable`: the ρ-weighted density core is integrable given `hsupp`.
- `finsum_pou_density_collapse_hsupp`: the PoU finsum of signed densities collapses to the
  single-chart signed density integral.
- `density_chart_invariant_form_supp`: oriented density integrals are chart-independent when
  the weight and form have disjoint-chart supports.
- `per_chart_density_to_c0`: each per-chart ρ-weighted density equals its `c₀`-chart version.
-/

open Bundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.InducedOrientNonzero
open Library.Geometry.Manifold.IntegralEquivFinsum
open Library.Geometry.Manifold.LocalCoeffDensity
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open MeasureTheory
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.PouDensityCollapse

/-- The product `(B.toSmoothPartitionOfUnity i ∘ chart.symm) * localCoeff φ (B.c i)` is
continuous on the chart target. Continuity of `localCoeff` follows from smoothness of
`formInCoord` composed with the continuous `topCoeff` projection; continuity of the bump
factor follows from smoothness of the partition of unity composed with `chart.symm`. -/
theorem weighted_core_continuous_on_target
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ιM : Type*} (B : SmoothBumpCovering ιM I N) (i : ιM) :
    ContinuousOn (fun y : EuclideanSpace ℝ (Fin d) =>
      B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
        * localCoeff φ (B.c i) y) (extChartAt I (B.c i)).target := by
  have h_lc : ContinuousOn (localCoeff φ (B.c i)) (extChartAt I (B.c i)).target := by
    have h_fic : ContDiffOn ℝ ∞ (formInCoord I φ (B.c i)) (extChartAt I (B.c i)).target :=
      form_in_coord_smooth I φ (B.c i)
    have h_top : Continuous (fun α : EuclideanSpace ℝ (Fin d) [⋀^Fin d]→L[ℝ] ℝ =>
        topCoeff α) := by simp only [topCoeff]; fun_prop
    exact h_top.comp_continuousOn h_fic.continuousOn
  have h_σ : ContinuousOn (extChartAt I (B.c i)).symm (extChartAt I (B.c i)).target :=
    continuousOn_extChartAt_symm (B.c i)
  have h_b : ContinuousOn (fun y => B.toSmoothPartitionOfUnity i
      ((extChartAt I (B.c i)).symm y)) (extChartAt I (B.c i)).target :=
    (B.toSmoothPartitionOfUnity i).prop.continuous.continuousOn.comp h_σ
      (fun y hy => (extChartAt I (B.c i)).map_target hy)
  exact h_b.mul h_lc

/-- The support of the bump-weighted local coefficient sits inside a compact subset `K` of
the chart target, and the integrand vanishes on `target \ K`. The compact witness is the
chart image of `tsupport (B.toSmoothPartitionOfUnity i)`, which is compact and contained
in the target; the bump factor vanishes outside it by definition. -/
theorem weighted_core_support_subset_compact
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ιM : Type*} (B : SmoothBumpCovering ιM I N) (i : ιM) :
    ∃ K, IsCompact K ∧ K ⊆ (extChartAt I (B.c i)).target ∧
      ∀ y ∈ (extChartAt I (B.c i)).target, y ∉ K →
        B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
          * localCoeff φ (B.c i) y = 0 := by
  refine ⟨extChartAt I (B.c i) '' tsupport (B.toSmoothPartitionOfUnity i),
    cross_core_chart_image_compact φ B B i i,
    cross_core_chart_image_subset_target φ B B i i, ?_⟩
  intro y hy hynot
  have h1 : B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y) = 0 := by
    apply image_eq_zero_of_notMem_tsupport
    intro hmem
    apply hynot
    rw [show y = extChartAt I (B.c i) ((extChartAt I (B.c i)).symm y) from
      (PartialEquiv.right_inv _ hy).symm]
    exact Set.mem_image_of_mem _ hmem
  rw [h1]; ring

/-- The bump-weighted local coefficient
`(B.toSmoothPartitionOfUnity i ∘ chart.symm) * localCoeff φ` is integrable on the chart
target. Continuity on the target (`weighted_core_continuous_on_target`) and compact support
in the target (`weighted_core_support_subset_compact`) together give integrability via
`ContinuousOn.integrableOn_compact'` extended by `of_forall_diff_eq_zero`. -/
theorem weighted_core_integrable_generic
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ιM : Type*} (B : SmoothBumpCovering ιM I N) (i : ιM) :
    IntegrableOn (fun y =>
      B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
        * localCoeff φ (B.c i) y)
      (extChartAt I (B.c i)).target volume := by
  have h_cont := weighted_core_continuous_on_target φ B i
  have h_supp := weighted_core_support_subset_compact φ B i
  have htmeas : MeasurableSet (extChartAt I (B.c i)).target := by
    rw [extChartAt_target]
    exact ((chartAt EH (B.c i)).open_target.preimage I.continuous_symm).measurableSet.inter
      I.isClosed_range.measurableSet
  obtain ⟨K, hKc, hKsub, hKvanish⟩ := h_supp
  exact ((h_cont.mono hKsub).integrableOn_compact' hKc hKc.measurableSet).of_forall_diff_eq_zero
    htmeas (fun y hy ↦ hKvanish y hy.1 hy.2)

/-- The full signed integrand
`(B.toSmoothPartitionOfUnity i ∘ chart.symm) * localCoeff φ * Real.sign (localCoeff refForm)`
is integrable on the chart target. The unsigned core is integrable by
`weighted_core_integrable_generic`; multiplying by the bounded measurable `Real.sign` factor
preserves integrability via `IntegrableOn.mul_bdd`. -/
theorem weighted_signed_integrand_integrable
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ιM : Type*} (B : SmoothBumpCovering ιM I N) (i : ιM) :
    IntegrableOn (fun y =>
      B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
        * localCoeff φ (B.c i) y
        * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y))
      (extChartAt I (B.c i)).target volume := by
  have h_core := weighted_core_integrable_generic φ B i
  have h_meas := sign_localcoeff_aestrongly_measurable B i
  have h_bound := sign_localcoeff_norm_le_one B i
  exact h_core.mul_bdd h_meas h_bound

/-- The ρ-weighted local coefficient `ρ i (chart.symm ·) * localCoeff g c₀` is integrable on
the chart target, given that `tsupport g ⊆ (chartAt EH c₀).source`. The compact witness is
the chart image of `tsupport g`; the `localCoeff` vanishes outside it because `g` vanishes
there. Integrability follows from `ContinuousOn.integrableOn_compact'` extended by
`of_forall_diff_eq_zero`. -/
theorem pou_density_core_integrable
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N]
    (g : DiffForm I N d) (c₀ : N)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt EH c₀).source)
    {ι : Type*} (ρ : SmoothPartitionOfUnity ι I N Set.univ) (i : ι) :
    MeasureTheory.IntegrableOn (fun y : EuclideanSpace ℝ (Fin d) =>
      ρ i ((extChartAt I c₀).symm y) * localCoeff g c₀ y)
      (extChartAt I c₀).target MeasureTheory.volume := by
  have h_lc : ContinuousOn (localCoeff g c₀) (extChartAt I c₀).target := by
    have h_fic : ContDiffOn ℝ ∞ (formInCoord I g c₀) (extChartAt I c₀).target :=
      form_in_coord_smooth I g c₀
    have h_top : Continuous (fun α : EuclideanSpace ℝ (Fin d) [⋀^Fin d]→L[ℝ] ℝ =>
        topCoeff α) := by simp only [topCoeff]; fun_prop
    exact h_top.comp_continuousOn h_fic.continuousOn
  have h_σ : ContinuousOn (extChartAt I c₀).symm (extChartAt I c₀).target :=
    continuousOn_extChartAt_symm c₀
  have h_b : ContinuousOn (fun y => ρ i ((extChartAt I c₀).symm y)) (extChartAt I c₀).target :=
    (ρ i).prop.continuous.continuousOn.comp h_σ
      (fun y hy => (extChartAt I c₀).map_target hy)
  have h_cont : ContinuousOn (fun y => ρ i ((extChartAt I c₀).symm y) * localCoeff g c₀ y)
      (extChartAt I c₀).target := h_b.mul h_lc
  have htmeas : MeasurableSet (extChartAt I c₀).target := by
    rw [extChartAt_target]
    exact ((chartAt EH c₀).open_target.preimage I.continuous_symm).measurableSet.inter
      I.isClosed_range.measurableSet
  have hsource : tsupport (fun x => g x) ⊆ (extChartAt I c₀).source := by
    rw [extChartAt_source]; exact hsupp
  have hcomp_g : IsCompact (tsupport (fun x => g x)) :=
    (isClosed_tsupport _).isCompact
  have hKc : IsCompact (extChartAt I c₀ '' tsupport (fun x => g x)) :=
    hcomp_g.image_of_continuousOn ((continuousOn_extChartAt c₀).mono hsource)
  have hKsub : extChartAt I c₀ '' tsupport (fun x => g x) ⊆ (extChartAt I c₀).target := by
    intro y hy
    obtain ⟨x, hx, rfl⟩ := hy
    exact (extChartAt I c₀).map_source (hsource hx)
  have hKvanish : ∀ y ∈ (extChartAt I c₀).target,
      y ∉ extChartAt I c₀ '' tsupport (fun x => g x) →
      ρ i ((extChartAt I c₀).symm y) * localCoeff g c₀ y = 0 := by
    intro y hy hynot
    have h_notmem : (extChartAt I c₀).symm y ∉ tsupport (fun x => g x) := by
      intro hmem
      apply hynot
      rw [show y = extChartAt I c₀ ((extChartAt I c₀).symm y) from
        (PartialEquiv.right_inv _ hy).symm]
      exact Set.mem_image_of_mem _ hmem
    have h_g : g ((extChartAt I c₀).symm y) = 0 :=
      image_eq_zero_of_notMem_tsupport h_notmem
    have h_lc_zero : localCoeff g c₀ y = 0 := by
      simp only [localCoeff, topCoeff, formInCoord, h_g, map_zero]
      simp
    rw [h_lc_zero]; ring
  exact ((h_cont.mono hKsub).integrableOn_compact' hKc hKc.measurableSet).of_forall_diff_eq_zero
    htmeas (fun y hy ↦ hKvanish y hy.1 hy.2)

/-- The `i`-support of the family
`fun i y ↦ ρ i (chart.symm y) * localCoeff g c₀ y * Real.sign (localCoeff refForm c₀ y)`
is finite. Since `ρ` is a `SmoothPartitionOfUnity` on the compact `N`, its index support
is finite; the product is nonzero at some `y` only if `ρ i` is nonzero. -/
theorem finsum_pou_collapse_support_finite
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N]
    (g : DiffForm I N d) (c₀ : N)
    {ι : Type*} (ρ : SmoothPartitionOfUnity ι I N Set.univ) (c : ι → N)
    (hρ : ρ.IsSubordinate (fun i => (chartAt EH (c i)).source)) :
    (Function.support (fun (i : ι) (y : EuclideanSpace ℝ (Fin d)) =>
      ρ i ((extChartAt I c₀).symm y) * localCoeff g c₀ y
        * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y))).Finite := by
  apply Set.Finite.subset (ρ.locallyFinite.finite_nonempty_of_compact)
  intro i hi
  rw [Function.mem_support] at hi
  obtain ⟨y, hy⟩ := Function.ne_iff.1 hi
  simp only [Pi.zero_apply] at hy
  refine ⟨(extChartAt I c₀).symm y, ?_⟩
  rw [Function.mem_support]
  intro hρi
  apply hy
  rw [hρi]
  ring

/-- Pointwise collapse: the finsum over `i` of
`ρ i (chart.symm y) * localCoeff g c₀ y * sign` equals `sign * localCoeff g c₀ y`. This
uses `ρ.sum_eq_one` to collapse `∑ᶠ i, ρ i p = 1`, then factors the common `localCoeff`
and `sign` terms out of the finsum. -/
theorem finsum_pou_pointwise_collapse
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N]
    (g : DiffForm I N d) (c₀ : N)
    {ι : Type*} (ρ : SmoothPartitionOfUnity ι I N Set.univ) :
    ∀ y : EuclideanSpace ℝ (Fin d),
      (∑ᶠ i, ρ i ((extChartAt I c₀).symm y) * localCoeff g c₀ y
        * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y))
      = Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y)
        * localCoeff g c₀ y := by
  intro y
  have hsum : ∑ᶠ i, ρ i ((extChartAt I c₀).symm y) = 1 :=
    ρ.sum_eq_one (Set.mem_univ _)
  have hfactor : ∀ i, ρ i ((extChartAt I c₀).symm y) * localCoeff g c₀ y *
      Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y) =
      ρ i ((extChartAt I c₀).symm y) *
      (localCoeff g c₀ y *
        Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y)) :=
    fun i => mul_assoc _ _ _
  simp_rw [hfactor, ← finsum_mul, hsum, one_mul, mul_comm]

/-- Each per-`i` signed integrand
`ρ i (chart.symm ·) * localCoeff g c₀ * Real.sign (localCoeff refForm c₀)` is integrable
on the chart target. The unsigned core is integrable by `pou_density_core_integrable`
(using `hsupp`); multiplying by the bounded measurable `Real.sign` factor preserves
integrability via `IntegrableOn.mul_bdd`. -/
theorem finsum_pou_collapse_integrable
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N]
    (g : DiffForm I N d) (c₀ : N)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt EH c₀).source)
    {ι : Type*} (ρ : SmoothPartitionOfUnity ι I N Set.univ) (c : ι → N)
    (hρ : ρ.IsSubordinate (fun i => (chartAt EH (c i)).source)) :
    ∀ i : ι, MeasureTheory.IntegrableOn (fun y : EuclideanSpace ℝ (Fin d) =>
      ρ i ((extChartAt I c₀).symm y) * localCoeff g c₀ y
        * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y))
      (extChartAt I c₀).target MeasureTheory.volume := by
  intro i
  have h_core := pou_density_core_integrable g c₀ hsupp ρ i
  have h_meas := sign_localcoeff_aestrongly_measurable_gen (I := I) (N := N) c₀
  have h_bound := sign_localcoeff_norm_le_one_gen (I := I) (N := N) c₀
  exact h_core.mul_bdd h_meas h_bound

/-- The finsum over `i` of the integrals of
`ρ i (chart.symm ·) * localCoeff g c₀ * sign` equals the single integral of
`sign * localCoeff g c₀` over the chart target. This swaps the finsum and integral (using
finite support and per-`i` integrability), then collapses the resulting pointwise finsum to
`sign * localCoeff g c₀` via `finsum_pou_pointwise_collapse`. -/
theorem finsum_pou_density_collapse_hsupp
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N]
    (g : DiffForm I N d) (c₀ : N)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt EH c₀).source)
    {ι : Type*} (ρ : SmoothPartitionOfUnity ι I N Set.univ) (c : ι → N)
    (hρ : ρ.IsSubordinate (fun i => (chartAt EH (c i)).source)) :
    (∑ᶠ i, ∫ y in (extChartAt I c₀).target,
        ρ i ((extChartAt I c₀).symm y) * localCoeff g c₀ y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y)
          ∂MeasureTheory.volume)
      = ∫ y in (extChartAt I c₀).target,
        Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y)
          * localCoeff g c₀ y
          ∂MeasureTheory.volume := by
  have h_support : (Function.support (fun (i : ι) (y : EuclideanSpace ℝ (Fin d)) =>
      ρ i ((extChartAt I c₀).symm y) * localCoeff g c₀ y
        * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y))).Finite :=
    finsum_pou_collapse_support_finite g c₀ ρ c hρ
  have h_integ : ∀ i : ι, MeasureTheory.IntegrableOn (fun y : EuclideanSpace ℝ (Fin d) =>
      ρ i ((extChartAt I c₀).symm y) * localCoeff g c₀ y
        * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y))
      (extChartAt I c₀).target MeasureTheory.volume :=
    finsum_pou_collapse_integrable g c₀ hsupp ρ c hρ
  have h_pt : ∀ y : EuclideanSpace ℝ (Fin d),
      (∑ᶠ i, ρ i ((extChartAt I c₀).symm y) * localCoeff g c₀ y
        * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y))
      = Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y)
        * localCoeff g c₀ y :=
    finsum_pou_pointwise_collapse g c₀ ρ
  rw [finsum_integral_swap_general (extChartAt I c₀).target MeasureTheory.volume _
    h_support h_integ]
  congr 1
  funext y
  exact h_pt y

/-- The oriented local density integral is chart-independent when the weight `w` is supported
in `(chartAt EH p).source` and the form `g` is supported in `(chartAt EH q).source`. The
proof chains three steps: slice the `p`-integral to the overlap region (via
`density_form_supp_lhs_slice`), apply the orientation-preserving change of variables between
the two overlap slices (via `oriented_density_slice_cov`), then extend the `q`-slice to the
full `q`-target (via `density_form_supp_rhs_restrict`). -/
theorem density_chart_invariant_form_supp
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [OrientedManifold I N]
    (g : DiffForm I N d) (p q : N) (w : N → ℝ)
    (hw : ContMDiff I 𝓘(ℝ, ℝ) ∞ w)
    (hwsupp : tsupport w ⊆ (chartAt EH p).source)
    (hgsupp : tsupport (fun x => g x) ⊆ (chartAt EH q).source) :
    ∫ y in (extChartAt I p).target,
        w ((extChartAt I p).symm y) * localCoeff g p y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) p y) ∂volume
      = ∫ z in (extChartAt I q).target,
        w ((extChartAt I q).symm z) * localCoeff g q z
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q z) ∂volume := by
  have h_lhs := density_form_supp_lhs_slice g p q w hw hgsupp
  have h_core := oriented_density_slice_cov g p q w hw hwsupp hgsupp
  have h_rhs := density_form_supp_rhs_restrict g p q w hw hwsupp
  exact h_lhs.trans (h_core.trans h_rhs)

/-- Each per-`i` ρ-weighted oriented density integral in chart `c i` equals the same density
read in the fixed chart `c₀`, given `tsupport g ⊆ (chartAt EH c₀).source`. This is an
instance of `density_chart_invariant_form_supp` with weight `ρ i` (supported in
`(chartAt EH (c i)).source` by `hρ i`) and form `g` (supported in `(chartAt EH c₀).source`
by `hsupp`). -/
theorem per_chart_density_to_c0
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N]
    (g : DiffForm I N d) (c₀ : N)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt EH c₀).source)
    {ι : Type*} (ρ : SmoothPartitionOfUnity ι I N Set.univ) (c : ι → N)
    (hρ : ρ.IsSubordinate (fun i => (chartAt EH (c i)).source)) :
    ∀ i, (∫ y in (extChartAt I (c i)).target,
        ρ i ((extChartAt I (c i)).symm y) * localCoeff g (c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (c i) y)
          ∂MeasureTheory.volume)
      = ∫ y in (extChartAt I c₀).target,
        ρ i ((extChartAt I c₀).symm y) * localCoeff g c₀ y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y)
          ∂MeasureTheory.volume := by
  intro i
  exact density_chart_invariant_form_supp g (c i) c₀ (ρ i) (ρ i).contMDiff (hρ i) hsupp

end Library.Geometry.Manifold.PouDensityCollapse
