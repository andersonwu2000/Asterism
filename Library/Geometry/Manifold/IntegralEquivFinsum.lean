import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.InducedOrientNonzero         -- inducedOrient, inducedOrient_ne_zero
import Library.Geometry.Manifold.LocalCoeffDensity
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBdry.PullbackBdryDefs         -- pullbackBdryFun
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff    -- contMDiff_pullbackBdryFun
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry
import Mathlib.Algebra.BigOperators.Finprod
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Data.Real.Sign
import Mathlib.Geometry.Manifold.BumpFunction
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.ContMDiff.Defs
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.PartitionOfUnity
import Mathlib.MeasureTheory.Function.StronglyMeasurable.AEStronglyMeasurable
import Mathlib.MeasureTheory.Integral.Bochner.Set
import Mathlib.MeasureTheory.Integral.IntegrableOn
import Mathlib.MeasureTheory.MeasurableSpace.Basic
import Mathlib.Topology.Algebra.Support
import Mathlib.Topology.Compactness.Compact

/-!
# Covering-independence of `DiffForm.integral`

This file establishes that `DiffForm.integral φ` — defined via a sealed choice of
subordinate `SmoothBumpCovering` — equals the localized-density finsum over any
explicitly supplied subordinate covering. The proof runs a double-finsum refinement
argument: insert one partition of unity, change charts via
`local_coeff_density_chart_invariant`, swap the finsum order, then collapse the
other partition of unity.

## Main statements

- `integral_eq_finsum_over_subordinate`: `DiffForm.integral φ` equals the explicit
  finsum over any subordinate `SmoothBumpCovering`.
- `cross_finsum_swap`: the double cross-term finsum is invariant under swapping the
  two covering indices (combines per-term chart change-of-variables with finsum
  commutativity).
- `finsum_integral_swap_general`: finite-support finsum/set-integral interchange.
-/

open Bundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.InducedOrientNonzero
open Library.Geometry.Manifold.LocalCoeffDensity
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open MeasureTheory
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.IntegralEquivFinsum

variable {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N]

/-- The function `y ↦ Real.sign (localCoeff refForm (B₁.c i) y)` is almost-everywhere
strongly measurable on the chart target, restricted to the Lebesgue measure. -/
theorem sign_localcoeff_aestrongly_measurable
    [CompactSpace N] [OrientedManifold I N]
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    (i : ι₁) :
    MeasureTheory.AEStronglyMeasurable
      (fun y : EuclideanSpace ℝ (Fin d) ↦
        Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y))
      (MeasureTheory.volume.restrict (extChartAt I (B₁.c i)).target) := by
  have h_fic : ContDiffOn ℝ ∞
        (formInCoord I (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i))
        (extChartAt I (B₁.c i)).target :=
    form_in_coord_smooth I (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i)
  have h_top : Continuous
      (fun α : EuclideanSpace ℝ (Fin d) [⋀^Fin d]→L[ℝ] ℝ ↦ topCoeff α) := by
    simp only [topCoeff]; fun_prop
  have h_lc : ContinuousOn
      (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i))
      (extChartAt I (B₁.c i)).target :=
    h_top.comp_continuousOn h_fic.continuousOn
  have htmeas : MeasurableSet (extChartAt I (B₁.c i)).target := by
    rw [extChartAt_target]
    exact ((chartAt EH (B₁.c i)).open_target.preimage I.continuous_symm).measurableSet.inter
      I.isClosed_range.measurableSet
  have h_aesm : MeasureTheory.AEStronglyMeasurable
      (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i))
      (MeasureTheory.volume.restrict (extChartAt I (B₁.c i)).target) :=
    h_lc.aestronglyMeasurable htmeas
  have h_sign : Measurable Real.sign := by
    unfold Real.sign
    exact (measurable_const.ite (measurableSet_lt measurable_id measurable_const)
      (measurable_const.ite (measurableSet_lt measurable_const measurable_id) measurable_const))
  exact (h_sign.comp_aemeasurable h_aesm.aemeasurable).aestronglyMeasurable

/-- `Real.sign` takes values in `{-1, 0, 1}`, so its norm is at most `1` almost everywhere. -/
theorem sign_localcoeff_norm_le_one
    [CompactSpace N] [OrientedManifold I N]
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    (i : ι₁) :
    ∀ᵐ y ∂(MeasureTheory.volume.restrict (extChartAt I (B₁.c i)).target),
      ‖Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y)‖ ≤ 1 := by
  apply Filter.Eventually.of_forall
  intro y
  obtain hn | hz | hp :=
    Real.sign_apply_eq (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y)
  · rw [hn]; norm_num
  · rw [hz]; norm_num
  · rw [hp]; norm_num

/-- The function `y ↦ Real.sign (localCoeff refForm c y)` is almost-everywhere strongly
measurable on the chart target at `c`, for any chart center `c : N`. -/
theorem sign_localcoeff_aestrongly_measurable_gen
    [CompactSpace N] [OrientedManifold I N]
    (c : N) :
    MeasureTheory.AEStronglyMeasurable
      (fun y : EuclideanSpace ℝ (Fin d) ↦
        Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c y))
      (MeasureTheory.volume.restrict (extChartAt I c).target) := by
  have h_fic : ContDiffOn ℝ ∞
        (formInCoord I (OrientedManifold.refForm (I := I) (N := N)) c)
        (extChartAt I c).target :=
    form_in_coord_smooth I (OrientedManifold.refForm (I := I) (N := N)) c
  have h_top : Continuous
      (fun α : EuclideanSpace ℝ (Fin d) [⋀^Fin d]→L[ℝ] ℝ ↦ topCoeff α) := by
    simp only [topCoeff]; fun_prop
  have h_lc : ContinuousOn
      (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c)
      (extChartAt I c).target :=
    h_top.comp_continuousOn h_fic.continuousOn
  have htmeas : MeasurableSet (extChartAt I c).target := by
    rw [extChartAt_target]
    exact ((chartAt EH c).open_target.preimage I.continuous_symm).measurableSet.inter
      I.isClosed_range.measurableSet
  have h_aesm : MeasureTheory.AEStronglyMeasurable
      (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c)
      (MeasureTheory.volume.restrict (extChartAt I c).target) :=
    h_lc.aestronglyMeasurable htmeas
  have h_sign : Measurable Real.sign := by
    unfold Real.sign
    exact (measurable_const.ite (measurableSet_lt measurable_id measurable_const)
      (measurable_const.ite (measurableSet_lt measurable_const measurable_id) measurable_const))
  exact (h_sign.comp_aemeasurable h_aesm.aemeasurable).aestronglyMeasurable

/-- `Real.sign` takes values in `{-1, 0, 1}`, so its norm is at most `1` almost everywhere,
for any chart center `c : N`. -/
theorem sign_localcoeff_norm_le_one_gen
    [CompactSpace N] [OrientedManifold I N]
    (c : N) :
    ∀ᵐ y ∂(MeasureTheory.volume.restrict (extChartAt I c).target),
      ‖Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c y)‖ ≤ 1 := by
  apply Filter.Eventually.of_forall
  intro y
  obtain hn | hz | hp :=
    Real.sign_apply_eq (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c y)
  · rw [hn]; norm_num
  · rw [hz]; norm_num
  · rw [hp]; norm_num

/-- Commutativity of nested `∑ᶠ` over real-valued functions with finite joint support. -/
theorem finsum_real_comm {α β : Type*}
    (f : α → β → ℝ)
    (hf : (Function.support (fun p : α × β ↦ f p.1 p.2)).Finite) :
    ∑ᶠ i, ∑ᶠ j, f i j = ∑ᶠ j, ∑ᶠ i, f i j := by
  have hf' : (Function.support (fun p : β × α ↦ f p.2 p.1)).Finite := by
    have heq : Function.support (fun p : β × α ↦ f p.2 p.1) =
        Prod.swap '' Function.support (fun p : α × β ↦ f p.1 p.2) := by
      ext ⟨b, a⟩; simp [Function.mem_support]
    rw [heq]; exact hf.image _
  rw [← finsum_curry (fun p : α × β ↦ f p.1 p.2) hf,
      ← finsum_curry (fun p : β × α ↦ f p.2 p.1) hf']
  exact (finsum_comp_equiv (Equiv.prodComm β α)).symm

/-- The chart image of the topological support of a partition-of-unity bump is compact. -/
theorem cross_core_chart_image_compact
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (i : ι₁) (j : ι₂) :
    IsCompact (extChartAt I (B₁.c i) '' tsupport (B₁.toSmoothPartitionOfUnity i)) := by
  have hsupp_sub : tsupport (B₁.toSmoothPartitionOfUnity i) ⊆ tsupport (B₁ i) :=
    closure_mono (SmoothBumpCovering.support_toSmoothPartitionOfUnity_subset B₁ i)
  have hcomp : IsCompact (tsupport (B₁ i)) := (B₁ i).hasCompactSupport.isCompact
  have hcomp_sub : IsCompact (tsupport (B₁.toSmoothPartitionOfUnity i)) :=
    hcomp.of_isClosed_subset (isClosed_tsupport _) hsupp_sub
  have hsource : tsupport (B₁.toSmoothPartitionOfUnity i) ⊆
      (extChartAt I (B₁.c i)).source :=
    hsupp_sub.trans (B₁ i).tsupport_subset_extChartAt_source
  exact hcomp_sub.image_of_continuousOn ((continuousOn_extChartAt (B₁.c i)).mono hsource)

/-- The chart image of the topological support of a partition-of-unity bump lies in the
chart target. -/
theorem cross_core_chart_image_subset_target
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (i : ι₁) (j : ι₂) :
    extChartAt I (B₁.c i) '' tsupport (B₁.toSmoothPartitionOfUnity i)
      ⊆ (extChartAt I (B₁.c i)).target := by
  have hsub : tsupport ⇑(B₁.toSmoothPartitionOfUnity i) ⊆
      (extChartAt I (B₁.c i)).source := by
    calc tsupport ⇑(B₁.toSmoothPartitionOfUnity i)
        ⊆ closure (Function.support ⇑(B₁ i)) :=
          closure_mono (B₁.support_toSmoothPartitionOfUnity_subset i)
      _ = tsupport ⇑(B₁ i) := rfl
      _ ⊆ (extChartAt I (B₁.c i)).source := (B₁ i).tsupport_subset_extChartAt_source
  intro y hy
  obtain ⟨x, hx, rfl⟩ := hy
  exact (extChartAt I (B₁.c i)).map_source (hsub hx)

/-- Off the chart image of `tsupport (B₁.toSmoothPartitionOfUnity i)`, the bump factor
vanishes, so the entire cross-core integrand is zero. -/
theorem cross_core_vanish_off_chart_image
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (i : ι₁) (j : ι₂) :
    ∀ y ∈ (extChartAt I (B₁.c i)).target,
      y ∉ extChartAt I (B₁.c i) '' tsupport (B₁.toSmoothPartitionOfUnity i) →
        (B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
          * B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₁.c i)).symm y))
          * localCoeff φ (B₁.c i) y = 0 := by
  intro y hy hynot
  have h1 : B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y) = 0 := by
    apply image_eq_zero_of_notMem_tsupport
    intro hmem
    apply hynot
    rw [show y = extChartAt I (B₁.c i) ((extChartAt I (B₁.c i)).symm y) from
      (PartialEquiv.right_inv _ hy).symm]
    exact Set.mem_image_of_mem _ hmem
  rw [h1]; ring

/-- The cross-core integrand has support contained in a compact subset of the chart target. -/
theorem cross_core_support_subset_compact
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (i : ι₁) (j : ι₂) :
    ∃ K, IsCompact K ∧ K ⊆ (extChartAt I (B₁.c i)).target ∧
      ∀ y ∈ (extChartAt I (B₁.c i)).target, y ∉ K →
        (B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
          * B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₁.c i)).symm y))
          * localCoeff φ (B₁.c i) y = 0 := by
  exact ⟨_, cross_core_chart_image_compact φ B₁ B₂ i j,
    cross_core_chart_image_subset_target φ B₁ B₂ i j,
    cross_core_vanish_off_chart_image φ B₁ B₂ i j⟩

/-- The cross-core integrand `bump₁ · bump₂ · localCoeff φ` is continuous on the chart target. -/
theorem cross_core_continuous_on_target
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (i : ι₁) (j : ι₂) :
    ContinuousOn (fun y : EuclideanSpace ℝ (Fin d) ↦
      (B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
        * B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₁.c i)).symm y))
        * localCoeff φ (B₁.c i) y) (extChartAt I (B₁.c i)).target := by
  have h_lc : ContinuousOn (localCoeff φ (B₁.c i)) (extChartAt I (B₁.c i)).target := by
    have h_fic : ContDiffOn ℝ ∞ (formInCoord I φ (B₁.c i)) (extChartAt I (B₁.c i)).target :=
      form_in_coord_smooth I φ (B₁.c i)
    have h_top : Continuous
        (fun α : EuclideanSpace ℝ (Fin d) [⋀^Fin d]→L[ℝ] ℝ ↦ topCoeff α) := by
      simp only [topCoeff]; fun_prop
    exact h_top.comp_continuousOn h_fic.continuousOn
  have h_σ : ContinuousOn (extChartAt I (B₁.c i)).symm (extChartAt I (B₁.c i)).target :=
    continuousOn_extChartAt_symm (B₁.c i)
  have h_b1 : ContinuousOn (fun y ↦ B₁.toSmoothPartitionOfUnity i
      ((extChartAt I (B₁.c i)).symm y)) (extChartAt I (B₁.c i)).target :=
    (B₁.toSmoothPartitionOfUnity i).prop.continuous.continuousOn.comp h_σ
      (fun y hy ↦ (extChartAt I (B₁.c i)).map_target hy)
  have h_b2 : ContinuousOn (fun y ↦ B₂.toSmoothPartitionOfUnity j
      ((extChartAt I (B₁.c i)).symm y)) (extChartAt I (B₁.c i)).target :=
    (B₂.toSmoothPartitionOfUnity j).prop.continuous.continuousOn.comp h_σ
      (fun y hy ↦ (extChartAt I (B₁.c i)).map_target hy)
  exact (h_b1.mul h_b2).mul h_lc

/-- The cross-core integrand `bump₁ · bump₂ · localCoeff φ` is integrable on the chart target.
The integrand is continuous with compact support inside the target, so integrability follows from
`ContinuousOn.integrableOn_compact'` extended by the vanishing outside the compact piece. -/
theorem cross_core_integrable_on_target
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (i : ι₁) (j : ι₂) :
    MeasureTheory.IntegrableOn (fun y : EuclideanSpace ℝ (Fin d) ↦
      (B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
        * B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₁.c i)).symm y))
        * localCoeff φ (B₁.c i) y)
      (extChartAt I (B₁.c i)).target MeasureTheory.volume := by
  have h_cont := cross_core_continuous_on_target φ B₁ B₂ i j
  obtain ⟨K, hKc, hKsub, hKvanish⟩ := cross_core_support_subset_compact φ B₁ B₂ i j
  have htmeas : MeasurableSet (extChartAt I (B₁.c i)).target := by
    rw [extChartAt_target]
    exact ((chartAt EH (B₁.c i)).open_target.preimage I.continuous_symm).measurableSet.inter
      I.isClosed_range.measurableSet
  exact ((h_cont.mono hKsub).integrableOn_compact' hKc hKc.measurableSet).of_forall_diff_eq_zero
    htmeas (fun y hy ↦ hKvanish y hy.1 hy.2)

/-- The family of cross summands (indexed by `ι₂`) has finite support, because `B₂` is a
`SmoothBumpCovering` on the compact manifold `N` and hence has a finite index type. -/
theorem cross_summand_fn_support_finite
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (i : ι₁) :
    (Function.support (fun (j : ι₂) (y : EuclideanSpace ℝ (Fin d)) ↦
      (B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
        * B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₁.c i)).symm y))
        * localCoeff φ (B₁.c i) y
        * Real.sign
          (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y))).Finite := by
  haveI := B₂.fintype
  exact Set.toFinite _

/-- Each summand in the cross-term finsum is integrable on the chart target. The integrand
splits as `core · sign`, where `core` is integrable (continuous with compact support) and
`sign` is bounded by `1` and a.e. strongly measurable. -/
theorem cross_summand_integrable_on_target
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (i : ι₁) :
    ∀ j : ι₂, MeasureTheory.IntegrableOn (fun y : EuclideanSpace ℝ (Fin d) ↦
      (B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
        * B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₁.c i)).symm y))
        * localCoeff φ (B₁.c i) y
        * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y))
      (extChartAt I (B₁.c i)).target MeasureTheory.volume := by
  intro j
  exact (cross_core_integrable_on_target φ B₁ B₂ i j).mul_bdd
    (sign_localcoeff_aestrongly_measurable B₁ i)
    (sign_localcoeff_norm_le_one B₁ i)

/-- For a finite-support family of integrable functions, the finsum and set-integral commute. -/
theorem finsum_integral_swap_general
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E] [MeasurableSpace E]
    {β : Type*} (s : Set E) (μ : MeasureTheory.Measure E)
    (g : β → E → ℝ)
    (hsupp : (Function.support g).Finite)
    (hint : ∀ j, MeasureTheory.IntegrableOn (g j) s μ) :
    (∑ᶠ j, ∫ y in s, g j y ∂μ) = ∫ y in s, (∑ᶠ j, g j y) ∂μ := by
  classical
  have hsub_int : Function.support (fun j ↦ ∫ y in s, g j y ∂μ) ⊆ ↑hsupp.toFinset := by
    intro j hj
    simp only [Function.mem_support, ne_eq] at hj
    by_contra hjc
    rw [Finset.mem_coe, Set.Finite.mem_toFinset, Function.mem_support, not_not] at hjc
    apply hj
    simp [hjc]
  have hpt : ∀ y, (∑ᶠ j, g j y) = ∑ j ∈ hsupp.toFinset, g j y := by
    intro y
    apply finsum_eq_finsetSum_of_support_subset
    intro j hj
    simp only [Function.mem_support, ne_eq] at hj
    by_contra hjc
    rw [Finset.mem_coe, Set.Finite.mem_toFinset, Function.mem_support, not_not] at hjc
    apply hj
    simp [hjc]
  rw [finsum_eq_finsetSum_of_support_subset _ hsub_int]
  simp_rw [hpt]
  exact (MeasureTheory.integral_finsetSum hsupp.toFinset (fun j _ ↦ hint j)).symm

/-- The finsum over `ι₂` and the set-integral over the chart target commute, because the
summand family has finite support (compact `N`) and each summand is integrable. -/
theorem finsum_setintegral_swap
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (i : ι₁) :
    (∑ᶠ j, ∫ y in (extChartAt I (B₁.c i)).target,
        (B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
          * B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₁.c i)).symm y))
          * localCoeff φ (B₁.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y)
          ∂MeasureTheory.volume)
    = ∫ y in (extChartAt I (B₁.c i)).target,
        (∑ᶠ j, (B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
          * B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₁.c i)).symm y))
          * localCoeff φ (B₁.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y))
          ∂MeasureTheory.volume := by
  exact finsum_integral_swap_general (extChartAt I (B₁.c i)).target MeasureTheory.volume _
    (cross_summand_fn_support_finite φ B₁ B₂ i)
    (cross_summand_integrable_on_target φ B₁ B₂ i)

/-- The inner `∑ᶠ j` over the cross-integrand collapses to the single-bump integrand via
`∑ᶠ j, B₂.toSmoothPartitionOfUnity j = 1`. -/
theorem cross_integrand_setintegral_eq
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (i : ι₁) :
    (∫ y in (extChartAt I (B₁.c i)).target,
        (∑ᶠ j, (B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
          * B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₁.c i)).symm y))
          * localCoeff φ (B₁.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y))
          ∂MeasureTheory.volume)
    = ∫ y in (extChartAt I (B₁.c i)).target,
        B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
          * localCoeff φ (B₁.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y)
          ∂MeasureTheory.volume := by
  congr 1
  funext y
  rw [← finsum_mul, ← finsum_mul, ← mul_finsum,
    B₂.toSmoothPartitionOfUnity.sum_eq_one (Set.mem_univ _), mul_one]

/-- The joint support of cross-term integrals over `ι₁ × ι₂` is finite, because both
`B₁` and `B₂` have finite index types on the compact manifold `N`. -/
theorem cross_term_support_finite
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    (hB₁ : B₁.IsSubordinate (fun x ↦ (chartAt EH x).source))
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (hB₂ : B₂.IsSubordinate (fun x ↦ (chartAt EH x).source)) :
    (Function.support (fun p : ι₁ × ι₂ ↦
      ∫ y in (extChartAt I (B₂.c p.2)).target,
        (B₂.toSmoothPartitionOfUnity p.2 ((extChartAt I (B₂.c p.2)).symm y)
          * B₁.toSmoothPartitionOfUnity p.1 ((extChartAt I (B₂.c p.2)).symm y))
          * localCoeff φ (B₂.c p.2) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₂.c p.2) y)
          ∂MeasureTheory.volume)).Finite := by
  haveI := B₁.fintype
  haveI := B₂.fintype
  exact Set.toFinite _

/-- The product of two smooth partition-of-unity bumps is `C^∞`. -/
theorem cross_weight_smooth
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (i : ι₁) (j : ι₂) :
    ContMDiff I 𝓘(ℝ, ℝ) ∞
      (fun x ↦ B₁.toSmoothPartitionOfUnity i x * B₂.toSmoothPartitionOfUnity j x) :=
  (B₁.toSmoothPartitionOfUnity i).contMDiff.mul (B₂.toSmoothPartitionOfUnity j).contMDiff

/-- Each `(i, j)` cross-term integral, computed in the `B₁.c i` chart, equals the same
integral computed in the `B₂.c j` chart. This is the Jacobian chart change-of-variables
given by `local_coeff_density_chart_invariant` with weight `w = B₁.PoU i · B₂.PoU j`. -/
theorem cross_term_chart_change
    [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    (hB₁ : B₁.IsSubordinate (fun x ↦ (chartAt EH x).source))
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (hB₂ : B₂.IsSubordinate (fun x ↦ (chartAt EH x).source))
    (i : ι₁) (j : ι₂) :
    (∫ y in (extChartAt I (B₁.c i)).target,
        (B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
          * B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₁.c i)).symm y))
          * localCoeff φ (B₁.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y)
          ∂MeasureTheory.volume)
    = ∫ y in (extChartAt I (B₂.c j)).target,
        (B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₂.c j)).symm y)
          * B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₂.c j)).symm y))
          * localCoeff φ (B₂.c j) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₂.c j) y)
          ∂MeasureTheory.volume := by
  have hw : ContMDiff I 𝓘(ℝ, ℝ) ∞
      (fun x ↦ B₁.toSmoothPartitionOfUnity i x * B₂.toSmoothPartitionOfUnity j x) :=
    cross_weight_smooth B₁ B₂ i j
  have hsupp : tsupport
      (fun x ↦ B₁.toSmoothPartitionOfUnity i x * B₂.toSmoothPartitionOfUnity j x)
      ⊆ (chartAt EH (B₁.c i)).source ∩ (chartAt EH (B₂.c j)).source :=
    (Set.subset_inter
    (tsupport_mul_subset_left.trans (hB₁.toSmoothPartitionOfUnity i))
    (tsupport_mul_subset_right.trans (hB₂.toSmoothPartitionOfUnity j)))
  rw [local_coeff_density_chart_invariant φ (B₁.c i) (B₂.c j)
      (fun x ↦ B₁.toSmoothPartitionOfUnity i x * B₂.toSmoothPartitionOfUnity j x) hw hsupp]
  refine setIntegral_congr_fun ?_ (fun z _ ↦ ?_)
  · rw [extChartAt_target]
    exact (((chartAt EH (B₂.c j)).open_target.preimage I.continuous_symm).measurableSet).inter
      I.isClosed_range.measurableSet
  · ring

/-- The double finsum over cross-term integrals is symmetric in the two covering indices:
swapping `∑ᶠ i, ∑ᶠ j` to `∑ᶠ j, ∑ᶠ i` via `finsum_real_comm`. -/
theorem cross_finsum_order_swap
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    (hB₁ : B₁.IsSubordinate (fun x ↦ (chartAt EH x).source))
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (hB₂ : B₂.IsSubordinate (fun x ↦ (chartAt EH x).source)) :
    (∑ᶠ i, ∑ᶠ j, ∫ y in (extChartAt I (B₂.c j)).target,
        (B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₂.c j)).symm y)
          * B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₂.c j)).symm y))
          * localCoeff φ (B₂.c j) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₂.c j) y)
          ∂MeasureTheory.volume)
    = ∑ᶠ j, ∑ᶠ i, ∫ y in (extChartAt I (B₂.c j)).target,
        (B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₂.c j)).symm y)
          * B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₂.c j)).symm y))
          * localCoeff φ (B₂.c j) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₂.c j) y)
          ∂MeasureTheory.volume :=
  finsum_real_comm _ (cross_term_support_finite φ B₁ hB₁ B₂ hB₂)

/-- Each per-`i` chart term equals the `∑ᶠ j` cross-term sum at the same chart, obtained by
inserting `B₂`'s partition of unity (which sums to `1`) and interchanging finsum with integral. -/
theorem term_eq_cross_at_chart
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (i : ι₁) :
    (∫ y in (extChartAt I (B₁.c i)).target,
        B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
          * localCoeff φ (B₁.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y)
          ∂MeasureTheory.volume)
    = ∑ᶠ j, ∫ y in (extChartAt I (B₁.c i)).target,
        (B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
          * B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₁.c i)).symm y))
          * localCoeff φ (B₁.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y)
          ∂MeasureTheory.volume :=
  ((finsum_setintegral_swap φ B₁ B₂ i).trans
    (cross_integrand_setintegral_eq φ B₁ B₂ i)).symm

/-- Insert `B₂`'s partition of unity into each `B₁`-chart term: the outer `∑ᶠ i` sum of
single-chart integrals equals the double sum `∑ᶠ i, ∑ᶠ j` of cross-term integrals. -/
theorem term_eq_finsum_cross
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N) :
    (∑ᶠ i, ∫ y in (extChartAt I (B₁.c i)).target,
        B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
          * localCoeff φ (B₁.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y)
          ∂MeasureTheory.volume)
    = ∑ᶠ i, ∑ᶠ j, ∫ y in (extChartAt I (B₁.c i)).target,
        (B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
          * B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₁.c i)).symm y))
          * localCoeff φ (B₁.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y)
          ∂MeasureTheory.volume :=
  finsum_congr (fun i ↦ term_eq_cross_at_chart φ B₁ B₂ i)

/-- The double cross-term finsum moves from `B₁`-charts to `B₂`-charts: a per-term
chart change-of-variables followed by swapping the finsum order. -/
theorem cross_finsum_swap
    [CompactSpace N] [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ι₁ : Type*} (B₁ : SmoothBumpCovering ι₁ I N)
    (hB₁ : B₁.IsSubordinate (fun x ↦ (chartAt EH x).source))
    {ι₂ : Type*} (B₂ : SmoothBumpCovering ι₂ I N)
    (hB₂ : B₂.IsSubordinate (fun x ↦ (chartAt EH x).source)) :
    (∑ᶠ i, ∑ᶠ j, ∫ y in (extChartAt I (B₁.c i)).target,
        (B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₁.c i)).symm y)
          * B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₁.c i)).symm y))
          * localCoeff φ (B₁.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₁.c i) y)
          ∂MeasureTheory.volume)
    = ∑ᶠ j, ∑ᶠ i, ∫ y in (extChartAt I (B₂.c j)).target,
        (B₂.toSmoothPartitionOfUnity j ((extChartAt I (B₂.c j)).symm y)
          * B₁.toSmoothPartitionOfUnity i ((extChartAt I (B₂.c j)).symm y))
          * localCoeff φ (B₂.c j) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₂.c j) y)
          ∂MeasureTheory.volume := by
  simp_rw [fun (i : ι₁) (j : ι₂) ↦ cross_term_chart_change φ B₁ hB₁ B₂ hB₂ i j]
  exact cross_finsum_order_swap φ B₁ hB₁ B₂ hB₂

/-- `DiffForm.integral φ` equals the localized-density finsum over any explicitly supplied
subordinate `SmoothBumpCovering`. The proof runs a double-finsum refinement: insert the
explicit covering's partition of unity into the sealed internal finsum, change charts, swap
the finsum order, then collapse the internal covering's partition of unity. -/
theorem integral_eq_finsum_over_subordinate
    [CompactSpace N] [OrientedManifold I N]
    {ι : Type*} (φ : DiffForm I N d)
    (B : SmoothBumpCovering ι I N Set.univ)
    (hB : B.IsSubordinate (fun x ↦ (chartAt EH x).source)) :
    DiffForm.integral φ = ∑ᶠ i, ∫ y in (extChartAt I (B.c i)).target,
        B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
          * localCoeff φ (B.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
          ∂MeasureTheory.volume := by
  set h := SmoothBumpCovering.exists_isSubordinate (I := I) (M := N)
      (s := (Set.univ : Set N)) isClosed_univ
      (U := fun x ↦ (chartAt EH x).source)
      (fun x _ ↦ (chartAt EH x).open_source.mem_nhds (mem_chart_source _ x)) with hh
  set B₀ := h.choose_spec.choose with hB0def
  have hB₀ : B₀.IsSubordinate (fun x ↦ (chartAt EH x).source) := h.choose_spec.choose_spec
  have hint : DiffForm.integral φ
      = ∑ᶠ i, ∫ y in (extChartAt I (B₀.c i)).target,
          B₀.toSmoothPartitionOfUnity i ((extChartAt I (B₀.c i)).symm y)
            * localCoeff φ (B₀.c i) y
            * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₀.c i) y)
            ∂MeasureTheory.volume := rfl
  exact hint.trans
    ((term_eq_finsum_cross φ B₀ B).trans
      ((cross_finsum_swap φ B₀ hB₀ B hB).trans
        (term_eq_finsum_cross φ B B₀).symm))

end Library.Geometry.Manifold.IntegralEquivFinsum
