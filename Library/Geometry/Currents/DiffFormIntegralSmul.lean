import Library.Geometry.Currents.PullbackFormBounded         -- pullbackFlatForm_integral_bounded (crux)
import Library.Geometry.Currents.BoundarySquareZero          -- Current
import Library.Geometry.Manifold.StokesIntegralDefs          -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.PullbackFlatDNat        -- pullbackFlatForm

/-!
# Scalar multiplication for differential form integration

This file proves that `DiffForm.integral` is homogeneous under scalar multiplication by a
real number: `DiffForm.integral (c • a) = c • DiffForm.integral a`.

The proof proceeds in three layers, mirroring the additive counterparts
`per_chart_integral_add` and `diffform_integral_add`:

1. `localCoeff_smul` — scalar multiplication commutes with `localCoeff` pointwise.
2. `per_chart_integral_smul` — the per-chart signed PoU-weighted integral scales by `c`.
3. `diffform_integral_smul_covering` — the covering-level `∑ᶠ` of chart integrals scales by `c`.
4. `diffform_integral_smul` — the top-level `DiffForm.integral` scales by `c`.

## Main statements

* `diffform_integral_smul` : `DiffForm.integral (c • a) = c • DiffForm.integral a`
-/

open Library.Geometry.Currents.BoundarySquareZero
open Library.Geometry.Currents.PullbackFormBounded
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.PullbackFlatDNat
open TopologicalSpace
open scoped Manifold Bundle ContDiff
open scoped Manifold Bundle ContDiff Distributions

namespace Library.Geometry.Currents.DiffFormIntegralSmul

/-- Scalar multiplication pulls through `localCoeff` via trivialization linearity:
`localCoeff (c • a) x y = c * localCoeff a x y`. The proof unfolds to `CLM.map_smul` followed
by `ContinuousAlternatingMap.smul_apply` on the basis vector. -/
theorem localCoeff_smul
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ((⊤ : ℕ∞) : WithTop ℕ∞) N]
    (c : ℝ) (a : Library.Geometry.Manifold.DiffFormBundle.DiffForm I N d)
    (x : N) (y : EuclideanSpace ℝ (Fin d)) :
    localCoeff (c • a) x y = c * localCoeff a x y := by
  simp only [localCoeff, topCoeff,
    Library.Geometry.Manifold.MExtDerivCoord.formInCoord]
  change (Bundle.Trivialization.continuousLinearMapAt ℝ
      (trivializationAt (EuclideanSpace ℝ (Fin d) [⋀^Fin d]→L[ℝ] ℝ)
        (formBundleCore I d).Fiber x)
      ((extChartAt I x).symm y)) (c • a ((extChartAt I x).symm y))
    ⇑(EuclideanSpace.basisFun (Fin d) ℝ) =
    c *
      ((Bundle.Trivialization.continuousLinearMapAt ℝ
          (trivializationAt (EuclideanSpace ℝ (Fin d) [⋀^Fin d]→L[ℝ] ℝ)
            (formBundleCore I d).Fiber x)
          ((extChartAt I x).symm y)) (a ((extChartAt I x).symm y)))
        ⇑(EuclideanSpace.basisFun (Fin d) ℝ)
  rw [map_smul]
  simp [ContinuousAlternatingMap.smul_apply, smul_eq_mul]

/-- Homogeneity of the per-chart signed PoU-weighted integral, mirroring `per_chart_integral_add`.
`localCoeff_smul` gives `localCoeff (c • a) = c * localCoeff a` pointwise; rewriting the
integrand to `c • (PoUᵢ · localCoeff a · sign)` lets `MeasureTheory.integral_smul` pull `c`
out. -/
theorem per_chart_integral_smul
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ((⊤ : ℕ∞) : WithTop ℕ∞) N] [CompactSpace N] [OrientedManifold I N]
    (c : ℝ) (a : Library.Geometry.Manifold.DiffFormBundle.DiffForm I N d)
    {ιM : Type*} (B : SmoothBumpCovering ιM I N)
    (_hB : B.IsSubordinate fun x => (chartAt EH x).source) :
    ∀ i,
      (∫ y in (extChartAt I (B.c i)).target,
          B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff (c • a) (B.c i) y
            * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
            ∂MeasureTheory.volume) =
      c • (∫ y in (extChartAt I (B.c i)).target,
          B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff a (B.c i) y
            * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
            ∂MeasureTheory.volume)  := by
  intro i
  have hsmul := localCoeff_smul c a
  have key :
      (∫ y in (extChartAt I (B.c i)).target,
          B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff (c • a) (B.c i) y
            * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
            ∂MeasureTheory.volume) =
      ∫ y in (extChartAt I (B.c i)).target,
        c • (B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff a (B.c i) y
            * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y))
        ∂MeasureTheory.volume := by
    congr 1
    funext y
    rw [hsmul]
    simp only [smul_eq_mul]
    ring
  rw [key, MeasureTheory.integral_smul]

/-- Homogeneity of the covering integral, mirroring `integral_add_over_covering`.
`per_chart_integral_smul` pulls `c` out of each chart integral, then `finsum_congr` and
`smul_finsum` pull `c` out of the `∑ᶠ`. -/
theorem diffform_integral_smul_covering
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ((⊤ : ℕ∞) : WithTop ℕ∞) N] [CompactSpace N] [OrientedManifold I N]
    (c : ℝ) (a : Library.Geometry.Manifold.DiffFormBundle.DiffForm I N d)
    {ιM : Type*} (B : SmoothBumpCovering ιM I N)
    (hB : B.IsSubordinate fun x => (chartAt EH x).source) :
    (∑ᶠ i, ∫ y in (extChartAt I (B.c i)).target,
        B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
          * localCoeff (c • a) (B.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
          ∂MeasureTheory.volume)
    = c • (∑ᶠ i, ∫ y in (extChartAt I (B.c i)).target,
        B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
          * localCoeff a (B.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
          ∂MeasureTheory.volume)  := by
  have hper := per_chart_integral_smul c a B hB
  rw [finsum_congr hper]
  exact (smul_finsum c _).symm

/-- **Homogeneity of `DiffForm.integral`**: `DiffForm.integral (c • a) = c • DiffForm.integral a`.
Mirrors `diffform_integral_add`. Both integrals are unfolded on the canonical bump covering `B₀`
(by `rfl`), then `diffform_integral_smul_covering` pulls `c` out of the `∑ᶠ`-integral. -/
theorem diffform_integral_smul
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ((⊤ : ℕ∞) : WithTop ℕ∞) N] [CompactSpace N] [OrientedManifold I N]
    (c : ℝ) (a : Library.Geometry.Manifold.DiffFormBundle.DiffForm I N d) :
    Library.Geometry.Manifold.StokesIntegralDefs.DiffForm.integral (c • a)
      = c • Library.Geometry.Manifold.StokesIntegralDefs.DiffForm.integral a  := by
  set h := SmoothBumpCovering.exists_isSubordinate
    (I := I) (M := N) (s := Set.univ) isClosed_univ
    (U := fun x => (chartAt EH x).source)
    (fun x _ => (chartAt EH x).open_source.mem_nhds (mem_chart_source _ x)) with hh
  set B₀ := h.choose_spec.choose with hBdef
  have hsub := h.choose_spec.choose_spec
  have e_ca : DiffForm.integral (c • a)
      = ∑ᶠ i, ∫ y in (extChartAt I (B₀.c i)).target,
          B₀.toSmoothPartitionOfUnity i ((extChartAt I (B₀.c i)).symm y)
            * localCoeff (c • a) (B₀.c i) y
            * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₀.c i) y)
            ∂MeasureTheory.volume := rfl
  have e_a : DiffForm.integral a
      = ∑ᶠ i, ∫ y in (extChartAt I (B₀.c i)).target,
          B₀.toSmoothPartitionOfUnity i ((extChartAt I (B₀.c i)).symm y)
            * localCoeff a (B₀.c i) y
            * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₀.c i) y)
            ∂MeasureTheory.volume := rfl
  rw [e_ca, e_a]
  exact diffform_integral_smul_covering c a B₀ hsub

end Library.Geometry.Currents.DiffFormIntegralSmul
