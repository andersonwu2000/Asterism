import Library.Geometry.Manifold.ChartTransition
import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.InducedOrientNonzero         -- inducedOrient, inducedOrient_ne_zero
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBdry.PullbackBdryDefs         -- pullbackBdryFun
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff    -- contMDiff_pullbackBdryFun
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry
import Mathlib.Analysis.Calculus.FDeriv.Basic
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.NormedSpace.Alternating.Basic
import Mathlib.Data.Real.Sign
import Mathlib.Geometry.Manifold.ContMDiff.Basic
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.LinearAlgebra.Determinant
import Mathlib.MeasureTheory.Function.Jacobian
import Mathlib.MeasureTheory.Integral.Bochner.Set
import Mathlib.MeasureTheory.Measure.Lebesgue.Basic
import Mathlib.Topology.Algebra.Module.Determinant
import Mathlib.Topology.Algebra.Support

/-!
# Local coefficient density chart invariance

This file shows that the oriented local-density integral of a differential form is invariant
under chart change. The argument factors into a Jacobian change-of-variables on the chart-overlap
slices and a pointwise sign/determinant identity that matches the two oriented densities.

## Main statements

- `top_coeff_comp_det`: composing a top-degree alternating form with a CLM `L` scales its
  standard-basis value by `L.det`.
- `local_coeff_pullback_det`: `localCoeff` transforms under chart change by the Jacobian
  determinant of the transition map.
- `mul_sign_mul_eq_abs_mul_sign`: the identity
  `c * (det * a) * sign(det * b) = c * (|det| * (a * sign b))`.
- `integrand_chart_change`: pointwise oriented-density chart-overlap identity (w-support version).
- `slice_integrand_chart_change`: pointwise chart-overlap identity using overlap-slice membership
  directly (no w-support case split).
- `slice_jacobian_cov`: support-free Jacobian CoV on the chart-overlap slices.
- `oriented_density_slice_cov`: oriented-density chart-overlap CoV, slice version.
- `density_form_supp_lhs_slice`: restricts the p-chart integral to the overlap slice via the
  support of the form coefficient.
- `density_form_supp_rhs_restrict`: restricts the q-chart integral to the overlap slice via the
  support of the weight.
- `local_coeff_density_chart_invariant`: full chart-overlap invariance of the oriented
  local-density integral.
-/

open Bundle MeasureTheory
open Library.Geometry.Manifold.ChartTransition
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.InducedOrientNonzero
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.LocalCoeffDensity

variable {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N]

/-- Composing a top-degree alternating form with a continuous linear map `L` scales its
evaluation on the standard Euclidean basis by `L.det`. -/
theorem top_coeff_comp_det
    (α : EuclideanSpace ℝ (Fin d) [⋀^Fin d]→L[ℝ] ℝ)
    (L : EuclideanSpace ℝ (Fin d) →L[ℝ] EuclideanSpace ℝ (Fin d)) :
    topCoeff (α.compContinuousLinearMap L) = L.det * topCoeff α := by
  simp only [topCoeff, ContinuousAlternatingMap.compContinuousLinearMap_apply]
  have heq : α.toAlternatingMap =
      α ⇑(EuclideanSpace.basisFun (Fin d) ℝ) •
      (EuclideanSpace.basisFun (Fin d) ℝ).toBasis.det :=
    AlternatingMap.eq_smul_basis_det (e := (EuclideanSpace.basisFun (Fin d) ℝ).toBasis)
      α.toAlternatingMap
  have step1 : α (⇑L ∘ ⇑(EuclideanSpace.basisFun (Fin d) ℝ)) =
      α.toAlternatingMap (⇑L ∘ ⇑(EuclideanSpace.basisFun (Fin d) ℝ)) := rfl
  rw [step1, heq]
  simp only [AlternatingMap.smul_apply]
  rw [show ⇑L ∘ ⇑(EuclideanSpace.basisFun (Fin d) ℝ) =
        ⇑L.toLinearMap ∘ ⇑(EuclideanSpace.basisFun (Fin d) ℝ) from rfl,
      Module.Basis.det_comp,
      ← OrthonormalBasis.coe_toBasis (EuclideanSpace.basisFun (Fin d) ℝ),
      Module.Basis.det_self, mul_one, smul_eq_mul]
  rw [← ContinuousLinearMap.det]
  ring

/-- `localCoeff` transforms under chart change by the Jacobian determinant of the transition map:
if `(extChartAt I p).symm y` lies in the source of the chart at `q`, then `localCoeff ψ p y`
equals `det(D(transition)) * localCoeff ψ q (transition y)`. -/
theorem local_coeff_pullback_det
    (ψ : DiffForm I N d) (p q : N)
    (y : EuclideanSpace ℝ (Fin d)) (hy : y ∈ (extChartAt I p).target)
    (hmem : (extChartAt I p).symm y ∈ (chartAt EH q).source) :
    localCoeff ψ p y
      = (fderivWithin ℝ (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm) (Set.range I) y).det
          * localCoeff ψ q (extChartAt I q ((extChartAt I p).symm y)) := by
  simp only [localCoeff]
  rw [form_in_coord_pullback I ψ p q y hy hmem]
  exact top_coeff_comp_det _ _

/-- Pure-ℝ algebra identity: `c * (det * a) * sign(det * b) = c * (|det| * (a * sign b))`.
This collapses the Jacobian sign against the orientation sign via a sign-of-product case split. -/
theorem mul_sign_mul_eq_abs_mul_sign (c detv a b : ℝ) :
    c * (detv * a) * Real.sign (detv * b)
      = c * (|detv| * (a * Real.sign b)) := by
  rcases lt_trichotomy detv 0 with hd | rfl | hd
  · rcases lt_trichotomy b 0 with hb | rfl | hb
    · rw [Real.sign_of_pos (mul_pos_of_neg_of_neg hd hb), abs_of_neg hd,
          Real.sign_of_neg hb]; ring
    · simp [Real.sign_zero]
    · rw [Real.sign_of_neg (mul_neg_of_neg_of_pos hd hb), abs_of_neg hd,
          Real.sign_of_pos hb]; ring
  · simp [abs_zero]
  · rcases lt_trichotomy b 0 with hb | rfl | hb
    · rw [Real.sign_of_neg (mul_neg_of_pos_of_neg hd hb), abs_of_pos hd,
          Real.sign_of_neg hb]; ring
    · simp [Real.sign_zero]
    · rw [Real.sign_of_pos (mul_pos hd hb), abs_of_pos hd,
          Real.sign_of_pos hb]; ring

/-- Pointwise chart-overlap identity for the oriented density integrand: on the overlap of the
p-chart and q-chart, the p-oriented density of `φ` weighted by `w` equals the q-oriented density
weighted by `w` and the absolute Jacobian of the transition map. -/
theorem integrand_chart_change
    [OrientedManifold I N]
    (φ : DiffForm I N d) (p q : N) (w : N → ℝ)
    (_hw : ContMDiff I 𝓘(ℝ, ℝ) ∞ w)
    (hsupp : tsupport w ⊆ (chartAt EH p).source ∩ (chartAt EH q).source)
    (y : EuclideanSpace ℝ (Fin d)) (hy : y ∈ (extChartAt I p).target) :
    w ((extChartAt I p).symm y) * localCoeff φ p y
        * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) p y)
      = w ((extChartAt I p).symm y) *
          (|(fderivWithin ℝ (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm)
                (Set.range I) y).det|
            * (localCoeff φ q (extChartAt I q ((extChartAt I p).symm y))
                * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q
                    (extChartAt I q ((extChartAt I p).symm y))))) := by
  rcases eq_or_ne (w ((extChartAt I p).symm y)) 0 with hw0 | hw0
  · rw [hw0]; ring
  · have hmem : (extChartAt I p).symm y ∈ (chartAt EH q).source := by
      have hmem' : (extChartAt I p).symm y ∈ tsupport w :=
        subset_tsupport w (by simpa [Function.mem_support] using hw0)
      exact (hsupp hmem').2
    have hφ := local_coeff_pullback_det φ p q y hy hmem
    have hμ := local_coeff_pullback_det
      (OrientedManifold.refForm (I := I) (N := N)) p q y hy hmem
    rw [hφ, hμ]
    exact mul_sign_mul_eq_abs_mul_sign _ _ _ _

/-- Pointwise chart-overlap oriented-density identity on the overlap slice. The slice membership
`hy.2` directly supplies `(extChartAt I p).symm y ∈ (chartAt EH q).source`, avoiding the
w-support case split used in `integrand_chart_change`. -/
theorem slice_integrand_chart_change
    [OrientedManifold I N]
    (φ : DiffForm I N d) (p q : N) (w : N → ℝ)
    (y : EuclideanSpace ℝ (Fin d))
    (hy : y ∈ (extChartAt I p).target ∩
        (extChartAt I p).symm ⁻¹' (chartAt EH q).source) :
    w ((extChartAt I p).symm y) * localCoeff φ p y
        * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) p y)
      = w ((extChartAt I p).symm y) *
          (|(fderivWithin ℝ (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm)
                (Set.range I) y).det|
            * (localCoeff φ q (extChartAt I q ((extChartAt I p).symm y))
                * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q
                    (extChartAt I q ((extChartAt I p).symm y))))) := by
  have hφ := local_coeff_pullback_det φ p q y hy.1 hy.2
  have hμ := local_coeff_pullback_det
    (OrientedManifold.refForm (I := I) (N := N)) p q y hy.1 hy.2
  rw [hφ, hμ]
  exact mul_sign_mul_eq_abs_mul_sign _ _ _ _

/-- Support-free Jacobian change of variables on the chart-overlap slices: the integral of
`w · g` over the q-overlap slice equals the integral of `w · (|det D(transition)| · g ∘ T)`
over the p-overlap slice, where `T = extChartAt I q ∘ (extChartAt I p).symm`. -/
theorem slice_jacobian_cov
    [OrientedManifold I N]
    (p q : N) (g : EuclideanSpace ℝ (Fin d) → ℝ) (w : N → ℝ) :
    ∫ z in (extChartAt I q).target ∩ (extChartAt I q).symm ⁻¹' (chartAt EH p).source,
        w ((extChartAt I q).symm z) * g z ∂volume
      = ∫ y in (extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source,
          w ((extChartAt I p).symm y) *
            (|(fderivWithin ℝ (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm)
                (Set.range I) y).det|
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

/-- Oriented-density chart-overlap change of variables, slice version: the p-overlap-slice
integral of the p-oriented density of `g` weighted by `w` equals the q-overlap-slice integral
of the q-oriented density of `g` weighted by `w`. -/
theorem oriented_density_slice_cov
    [OrientedManifold I N]
    (g : DiffForm I N d) (p q : N) (w : N → ℝ)
    (_hw : ContMDiff I 𝓘(ℝ, ℝ) ∞ w)
    (_hwsupp : tsupport w ⊆ (chartAt EH p).source)
    (_hgsupp : tsupport (fun x => g x) ⊆ (chartAt EH q).source) :
    (∫ y in (extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source,
        w ((extChartAt I p).symm y) * localCoeff g p y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) p y) ∂volume)
      = ∫ z in (extChartAt I q).target ∩ (extChartAt I q).symm ⁻¹' (chartAt EH p).source,
          w ((extChartAt I q).symm z) * localCoeff g q z
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q z) ∂volume := by
  have hmeas : MeasurableSet
      ((extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source) :=
    overlap_slice_measurable p q
  have hA :
      (∫ z in (extChartAt I q).target ∩ (extChartAt I q).symm ⁻¹' (chartAt EH p).source,
          w ((extChartAt I q).symm z) *
            (localCoeff g q z
              * Real.sign
                  (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q z)) ∂volume)
      = ∫ y in (extChartAt I p).target ∩ (extChartAt I p).symm ⁻¹' (chartAt EH q).source,
          w ((extChartAt I p).symm y) *
            (|(fderivWithin ℝ (↑(extChartAt I q) ∘ ↑(extChartAt I p).symm)
                (Set.range I) y).det|
              * (localCoeff g q (extChartAt I q ((extChartAt I p).symm y))
                  * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q
                      (extChartAt I q ((extChartAt I p).symm y))))) ∂volume :=
    slice_jacobian_cov p q
      (fun z => localCoeff g q z
        * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q z)) w
  rw [show (∫ z in (extChartAt I q).target ∩
          (extChartAt I q).symm ⁻¹' (chartAt EH p).source,
        w ((extChartAt I q).symm z) * localCoeff g q z
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q z) ∂volume)
      = ∫ z in (extChartAt I q).target ∩
          (extChartAt I q).symm ⁻¹' (chartAt EH p).source,
          w ((extChartAt I q).symm z) * (localCoeff g q z
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q z)) ∂volume
      from by simp only [mul_assoc]]
  rw [hA]
  exact setIntegral_congr_fun hmeas
    (fun y hy => slice_integrand_chart_change g p q w y hy)

/-- The p-chart integral of the p-oriented density of `g` weighted by `w` equals the same
integral restricted to the overlap slice `(extChartAt I p).target ∩ symm⁻¹' q.source`,
because `localCoeff g p y = 0` for points outside q's chart source (where `g` vanishes). -/
theorem density_form_supp_lhs_slice
    [OrientedManifold I N]
    (g : DiffForm I N d) (p q : N) (w : N → ℝ)
    (_hw : ContMDiff I 𝓘(ℝ, ℝ) ∞ w)
    (hgsupp : tsupport (fun x => g x) ⊆ (chartAt EH q).source) :
    (∫ y in (extChartAt I p).target,
        w ((extChartAt I p).symm y) * localCoeff g p y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) p y) ∂volume)
      = ∫ y in (extChartAt I p).target ∩
          (extChartAt I p).symm ⁻¹' (chartAt EH q).source,
          w ((extChartAt I p).symm y) * localCoeff g p y
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) p y) ∂volume := by
  apply setIntegral_eq_of_subset_of_forall_diff_eq_zero
  · rw [extChartAt_target]
    exact ((chartAt EH p).open_target.preimage I.continuous_symm).measurableSet.inter
      I.isClosed_range.measurableSet
  · exact Set.inter_subset_left
  · intro y hy
    have hnotin : (extChartAt I p).symm y ∉ (chartAt EH q).source := by
      intro habs; exact hy.2 ⟨hy.1, habs⟩
    have h_notmem : (extChartAt I p).symm y ∉ tsupport (fun x => g x) :=
      fun h => hnotin (hgsupp h)
    have h_g : g ((extChartAt I p).symm y) = 0 :=
      image_eq_zero_of_notMem_tsupport h_notmem
    have h_lc_zero : localCoeff g p y = 0 := by
      simp only [localCoeff, topCoeff, formInCoord, h_g, map_zero]
      simp
    rw [h_lc_zero, mul_zero, zero_mul]

/-- The q-chart integral of the q-oriented density of `g` weighted by `w` restricted to the
overlap slice equals the full q-chart integral, because `w` vanishes outside p's chart source. -/
theorem density_form_supp_rhs_restrict
    [OrientedManifold I N]
    (g : DiffForm I N d) (p q : N) (w : N → ℝ)
    (_hw : ContMDiff I 𝓘(ℝ, ℝ) ∞ w)
    (hwsupp : tsupport w ⊆ (chartAt EH p).source) :
    (∫ z in (extChartAt I q).target ∩ (extChartAt I q).symm ⁻¹' (chartAt EH p).source,
        w ((extChartAt I q).symm z) * localCoeff g q z
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q z) ∂volume)
      = ∫ z in (extChartAt I q).target,
          w ((extChartAt I q).symm z) * localCoeff g q z
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q z) ∂volume := by
  symm
  apply setIntegral_eq_of_subset_of_forall_diff_eq_zero
  · rw [extChartAt_target]
    exact ((chartAt EH q).open_target.preimage I.continuous_symm).measurableSet.inter
      I.isClosed_range.measurableSet
  · exact Set.inter_subset_left
  · intro z hz
    have hnotin : (extChartAt I q).symm z ∉ (chartAt EH p).source := by
      intro habs; exact hz.2 ⟨hz.1, habs⟩
    have hw0 : w ((extChartAt I q).symm z) = 0 :=
      image_eq_zero_of_notMem_tsupport (fun h => hnotin (hwsupp h))
    rw [hw0, zero_mul, zero_mul]

/-- **Local coefficient density chart invariance**: the oriented local-density integral is
chart-invariant. If `tsupport w` is contained in the intersection of the p-chart and q-chart
sources, then the p-chart and q-chart integrals of the oriented density of `φ` weighted by
`w` agree. -/
theorem local_coeff_density_chart_invariant
    [OrientedManifold I N]
    (φ : DiffForm I N d) (p q : N) (w : N → ℝ)
    (hw : ContMDiff I 𝓘(ℝ, ℝ) ∞ w)
    (hsupp : tsupport w ⊆ (chartAt EH p).source ∩ (chartAt EH q).source) :
    ∫ y in (extChartAt I p).target,
        w ((extChartAt I p).symm y) * localCoeff φ p y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) p y) ∂volume
      = ∫ z in (extChartAt I q).target,
          w ((extChartAt I q).symm z) * localCoeff φ q z
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q z) ∂volume := by
  have hA := chart_overlap_change_of_variables (I := I) p q
      (fun z => localCoeff φ q z *
        Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q z)) w hw hsupp
  have hmeas : MeasurableSet (extChartAt I p).target := by
    rw [extChartAt_target]
    exact (((chartAt EH p).open_target.preimage I.continuous_symm).measurableSet).inter
      I.isClosed_range.measurableSet
  rw [show (∫ z in (extChartAt I q).target,
        w ((extChartAt I q).symm z) * localCoeff φ q z
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q z) ∂volume)
      = ∫ z in (extChartAt I q).target,
          w ((extChartAt I q).symm z) * (localCoeff φ q z
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) q z)) ∂volume
      from by simp only [mul_assoc]]
  rw [hA]
  exact setIntegral_congr_fun hmeas (fun y hy =>
    integrand_chart_change (I := I) φ p q w hw hsupp y hy)

end Library.Geometry.Manifold.LocalCoeffDensity
