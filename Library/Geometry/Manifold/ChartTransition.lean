import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.InducedOrientNonzero         -- inducedOrient, inducedOrient_ne_zero
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBdry.PullbackBdryDefs         -- pullbackBdryFun
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff    -- contMDiff_pullbackBdryFun
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.Calculus.FDeriv.Basic
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Geometry.Manifold.ContMDiff.Basic
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Logic.Equiv.PartialEquiv
import Mathlib.MeasureTheory.Function.Jacobian
import Mathlib.MeasureTheory.Integral.Bochner.Set
import Mathlib.MeasureTheory.Measure.Lebesgue.Basic
import Mathlib.Topology.Algebra.Support

/-! # Chart Transition Lemmas

This file collects auxiliary results about chart transitions on smooth manifolds used in the
proof of Stokes' theorem. The central theme is that integrals localised to a function supported
in the intersection of two chart domains can be transformed via the chart transition map and its
Jacobian determinant.

## Main statements

- `overlap_slice_measurable`: the chart-overlap slice is a measurable set.
- `(Set.inter_subset_left.trans (extChartAt_target_subset_range `:)) overlap slice is contained in `Set.range I`.
- `transition_differentiablewithin_range`: the chart transition is differentiable within
  `Set.range I` at each point of the overlap slice.
- `transition_hasfderivwithin_overlap`: the transition has `fderivWithin … (range I)` as its
  within-slice Fréchet derivative.
- `transition_injOn_overlap`: the chart transition is injective on the overlap slice.
- `transition_left_inv_overlap`: `σ_q.symm ∘ σ_q` is the identity on the overlap slice.
- `transition_image_overlap_slice`: the transition maps the p-side overlap slice onto the
  q-side overlap slice.
- `restrict_p_to_overlap` / `restrict_q_to_overlap`: support restriction reduces full-target
  integrals to overlap-slice integrals.
- `integral_overlap_chart_transition`: change of variables for the transition map on overlap slices.
- `chart_overlap_change_of_variables`: the full chart-overlap Jacobian change-of-variables
  formula.
-/

open Bundle MeasureTheory
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.InducedOrientNonzero
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open scoped Manifold Bundle ContDiff Topology

namespace Library.Geometry.Manifold.ChartTransition

variable {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [OrientedManifold I N]

/-- The intersection of an extended chart target with the preimage of another chart's source
is a measurable set. -/
theorem overlap_slice_measurable (p q : N) :
    MeasurableSet
        ((extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source) := by
  have heq : (extChartAt I p).target ∩ ↑(extChartAt I p).symm ⁻¹' (chartAt EH q).source =
      I.symm ⁻¹' ((chartAt EH p).target ∩ ↑(chartAt EH p).symm ⁻¹' (chartAt EH q).source)
        ∩ Set.range I := by
    rw [extChartAt_target]
    have hcoe : (↑(extChartAt I p).symm : EuclideanSpace ℝ (Fin d) → N) =
        ↑(chartAt EH p).symm ∘ I.symm := rfl
    rw [hcoe, Set.preimage_comp]
    ext y
    simp [Set.mem_inter_iff, Set.mem_preimage, Set.mem_range, and_assoc, and_comm, and_left_comm]
  rw [heq]
  exact ((chartAt EH p).isOpen_inter_preimage_symm (chartAt EH q).open_source
      |>.preimage I.continuous_symm).measurableSet.inter I.isClosed_range.measurableSet

/-- The chart transition map `extChartAt q ∘ (extChartAt p).symm` is differentiable within
`Set.range I` at every point of the p-side chart-overlap slice. -/
theorem transition_differentiablewithin_range (p q : N)
    (y : EuclideanSpace ℝ (Fin d))
    (hy : y ∈ (extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source) :
    DifferentiableWithinAt ℝ (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm) (Set.range I) y := by
  obtain ⟨hy_tgt, hy_pre⟩ := hy
  have hsrc : ((extChartAt I p).symm ≫ extChartAt I q).source
      = (extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source := by
    simp [PartialEquiv.trans_source]
  have hcd : ContDiffOn ℝ ∞ (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm)
      ((extChartAt I p).symm ≫ extChartAt I q).source :=
    contDiffOn_ext_coord_change (I := I) q p
  have hdo : DifferentiableOn ℝ (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm)
      ((extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source) := by
    have := hcd.differentiableOn (by norm_num)
    rwa [hsrc] at this
  have htgt_mem : (extChartAt I p).target ∈ 𝓝[Set.range I] y :=
    extChartAt_target_mem_nhdsWithin_of_mem hy_tgt
  have hU : (extChartAt I p).symm ⁻¹' (chartAt EH q).source ∈ 𝓝[Set.range I] y := by
    have heq : 𝓝[Set.range I] y = 𝓝[(extChartAt I p).target] y := by
      rw [nhdsWithin_restrict'' (Set.range I) htgt_mem,
        Set.inter_eq_right.mpr (extChartAt_target_subset_range p)]
    rw [heq]
    exact (continuousOn_extChartAt_symm p y hy_tgt).preimage_mem_nhdsWithin
      ((chartAt EH q).open_source.mem_nhds hy_pre)
  exact (hdo y ⟨hy_tgt, hy_pre⟩).mono_of_mem_nhdsWithin (Filter.inter_mem htgt_mem hU)

/-- At each point of the p-side chart-overlap slice, the transition map has
`fderivWithin ℝ (extChartAt q ∘ (extChartAt p).symm) (Set.range I)` as its within-slice
Fréchet derivative. -/
theorem transition_hasfderivwithin_overlap (p q : N)
    (y : EuclideanSpace ℝ (Fin d))
    (hy : y ∈ (extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source) :
    HasFDerivWithinAt (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm)
      (fderivWithin ℝ (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm) (Set.range I) y)
      ((extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source) y := by
  have h_subset :
      (extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source
        ⊆ Set.range I := (Set.inter_subset_left.trans (extChartAt_target_subset_range p))
  exact (transition_differentiablewithin_range p q y hy).hasFDerivWithinAt.mono h_subset

/-- The chart transition map is injective on the p-side chart-overlap slice. -/
theorem transition_injOn_overlap (p q : N) :
    Set.InjOn (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm)
        ((extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source) := by
  apply Set.InjOn.comp
  · exact (extChartAt I q).injOn
  · exact ((extChartAt I p).symm.injOn).mono Set.inter_subset_left
  · intro y hy
    rw [extChartAt_source I q]; exact hy.2

/-- On the p-side chart-overlap slice, composing `(extChartAt q).symm` with `extChartAt q`
yields the identity, recovering `(extChartAt p).symm y`. -/
theorem transition_left_inv_overlap (p q : N)
    (y : EuclideanSpace ℝ (Fin d))
    (hy : y ∈ (extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source) :
    (extChartAt I q).symm (extChartAt I q ((extChartAt I p).symm y))
      = (extChartAt I p).symm y := by
  apply (extChartAt I q).left_inv
  rw [extChartAt_source]
  exact hy.2

/-- The chart transition map carries the p-side overlap slice onto the q-side overlap slice. -/
theorem transition_image_overlap_slice (p q : N) :
    (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm) ''
        ((extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source)
      = (extChartAt I q).target ∩ (extChartAt I q).symm ⁻¹' (chartAt EH p).source := by
  have hsrc : ((extChartAt I p).symm.trans (extChartAt I q)).source
      = (extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source := by
    rw [PartialEquiv.trans_source, PartialEquiv.symm_source, extChartAt_source]
  have htgt : ((extChartAt I p).symm.trans (extChartAt I q)).target
      = (extChartAt I q).target ∩ (extChartAt I q).symm ⁻¹' (chartAt EH p).source := by
    rw [PartialEquiv.trans_target, PartialEquiv.symm_target, extChartAt_source]
  rw [← hsrc, ← htgt, ← PartialEquiv.coe_trans]
  exact PartialEquiv.image_source_eq_target _

/-- Support restriction for the p-chart: when `tsupport w` is contained in both chart sources,
the full-target p-chart integral equals the integral over the overlap slice. -/
theorem restrict_p_to_overlap (p q : N) (g : EuclideanSpace ℝ (Fin d) → ℝ) (w : N → ℝ)
    (_hw : ContMDiff I 𝓘(ℝ, ℝ) ∞ w)
    (hsupp : tsupport w ⊆ (chartAt EH p).source ∩ (chartAt EH q).source) :
    ∫ y in (extChartAt I p).target,
        w ((extChartAt I p).symm y) *
          (|(fderivWithin ℝ (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm) (Set.range I) y).det|
            * g (extChartAt I q ((extChartAt I p).symm y))) ∂volume
      = ∫ y in (extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source,
          w ((extChartAt I p).symm y) *
            (|(fderivWithin ℝ (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm) (Set.range I) y).det|
              * g (extChartAt I q ((extChartAt I p).symm y))) ∂volume := by
  apply setIntegral_eq_of_subset_of_forall_diff_eq_zero ?_ Set.inter_subset_left
  · intro y hy
    have hyq : (extChartAt I p).symm y ∉ (chartAt EH q).source := by
      intro hmem
      exact hy.2 ⟨hy.1, hmem⟩
    have hw0 : w ((extChartAt I p).symm y) = 0 :=
      image_eq_zero_of_notMem_tsupport (fun hc => hyq (hsupp hc).2)
    rw [hw0, zero_mul]
  · rw [extChartAt_target]
    exact ((chartAt EH p).open_target.preimage I.continuous_symm).measurableSet.inter
      I.isClosed_range.measurableSet

/-- Support restriction for the q-chart: when `tsupport w` is contained in both chart sources,
the full-target q-chart integral equals the integral over the overlap slice. -/
theorem restrict_q_to_overlap (p q : N) (g : EuclideanSpace ℝ (Fin d) → ℝ) (w : N → ℝ)
    (_hw : ContMDiff I 𝓘(ℝ, ℝ) ∞ w)
    (hsupp : tsupport w ⊆ (chartAt EH p).source ∩ (chartAt EH q).source) :
    ∫ z in (extChartAt I q).target,
        w ((extChartAt I q).symm z) * g z ∂volume
      = ∫ z in (extChartAt I q).target ∩ (extChartAt I q).symm ⁻¹' (chartAt EH p).source,
          w ((extChartAt I q).symm z) * g z ∂volume := by
  apply setIntegral_eq_of_subset_of_forall_diff_eq_zero ?_ Set.inter_subset_left
  · intro z hz
    have hzp : (extChartAt I q).symm z ∉ (chartAt EH p).source := by
      intro hmem
      exact hz.2 ⟨hz.1, hmem⟩
    have hw0 : w ((extChartAt I q).symm z) = 0 :=
      image_eq_zero_of_notMem_tsupport (fun hc => hzp (hsupp hc).1)
    rw [hw0, zero_mul]
  · rw [extChartAt_target]
    exact ((chartAt EH q).open_target.preimage I.continuous_symm).measurableSet.inter
      I.isClosed_range.measurableSet

/-- Change of variables on chart-overlap slices: the q-side overlap integral equals the p-side
overlap integral weighted by the absolute Jacobian determinant of the chart transition map. -/
theorem integral_overlap_chart_transition (p q : N) (g : EuclideanSpace ℝ (Fin d) → ℝ)
    (w : N → ℝ) (_hw : ContMDiff I 𝓘(ℝ, ℝ) ∞ w)
    (_hsupp : tsupport w ⊆ (chartAt EH p).source ∩ (chartAt EH q).source) :
    ∫ z in (extChartAt I q).target ∩ (extChartAt I q).symm ⁻¹' (chartAt EH p).source,
        w ((extChartAt I q).symm z) * g z ∂volume
      = ∫ y in (extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source,
          w ((extChartAt I p).symm y) *
            (|(fderivWithin ℝ (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm) (Set.range I) y).det|
              * g (extChartAt I q ((extChartAt I p).symm y))) ∂volume := by
  have himg := transition_image_overlap_slice (I := I) p q
  have hmeas := overlap_slice_measurable (I := I) p q
  have hderiv := transition_hasfderivwithin_overlap (I := I) p q
  have hinj := transition_injOn_overlap (I := I) p q
  have hpt := transition_left_inv_overlap (I := I) p q
  rw [← himg, integral_image_eq_integral_abs_det_fderiv_smul volume hmeas hderiv hinj
        (fun z => w ((extChartAt I q).symm z) * g z)]
  apply setIntegral_congr_fun hmeas
  intro y hy
  simp only [Function.comp_apply, smul_eq_mul]
  rw [hpt y hy]
  ring

/-- **Chart-overlap change of variables**: the q-chart integral of `w(σ_q.symm z) * g z`
equals the p-chart integral weighted by the absolute Jacobian determinant of the chart
transition map, provided `tsupport w` is contained in the intersection of both chart sources. -/
theorem chart_overlap_change_of_variables (p q : N) (g : EuclideanSpace ℝ (Fin d) → ℝ)
    (w : N → ℝ) (hw : ContMDiff I 𝓘(ℝ, ℝ) ∞ w)
    (hsupp : tsupport w ⊆ (chartAt EH p).source ∩ (chartAt EH q).source) :
    ∫ z in (extChartAt I q).target,
        w ((extChartAt I q).symm z) * g z ∂volume
      = ∫ y in (extChartAt I p).target,
          w ((extChartAt I p).symm y) *
            (|(fderivWithin ℝ (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm) (Set.range I) y).det|
              * g (extChartAt I q ((extChartAt I p).symm y))) ∂volume := by
  rw [restrict_q_to_overlap p q g w hw hsupp, restrict_p_to_overlap p q g w hw hsupp]
  exact integral_overlap_chart_transition p q g w hw hsupp

end Library.Geometry.Manifold.ChartTransition
