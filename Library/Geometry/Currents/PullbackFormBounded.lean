import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.PullbackFlatDNat         -- pullbackFlatForm
import Library.Geometry.Currents.PullbackFormBoundAux
import Library.Geometry.Manifold.IntegralEquivFinsum

/-!
# Integral bound for the flat-form pullback

This file proves that `DiffForm.integral (pullbackFlatForm e ψ he hψ)` is bounded by `C * M`
whenever `‖ψ y‖ ≤ M` for all `y`, where `C ≥ 0` depends only on the smooth map
`e : N → F` and the compact manifold-with-boundary `N`.

## Main statements

- `pullbackFlatForm_integral_bounded`: for a smooth map `e : N → F` and any smooth family
  `ψ : F → (F [⋀^Fin (n + 1)]→L[ℝ] ℝ)` with uniform bound `‖ψ y‖ ≤ M`, there exists
  `C ≥ 0` such that `|DiffForm.integral (pullbackFlatForm e ψ he hψ)| ≤ C * M`.

## Implementation notes

The bound is assembled chart by chart via a finite smooth bump covering `B` of `N`.
`pullback_pointwise_coord_bound` gives a pointwise estimate on the local coefficient using
the operator norm of the chart derivative. `chart_term_bound` integrates this over the
compact image of the partition-of-unity tsupport. `finsum_assembly` collects the per-chart
bounds into the global estimate using the finite-sum structure of `DiffForm.integral`.
-/

open Library.Geometry.Currents.PullbackFormBoundAux
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.PullbackFlatDNat
open MeasureTheory
open scoped Manifold Bundle ContDiff
open scoped Manifold ContDiff

namespace Library.Geometry.Currents.PullbackFormBounded

/-- Bounds `|topCoeff α| ≤ ‖α‖` via the operator norm applied to the orthonormal basis
of `EuclideanSpace ℝ (Fin d)`, whose elements all have unit norm. -/
theorem topcoeff_le_norm {d : ℕ}
    (α : EuclideanSpace ℝ (Fin d) [⋀^Fin d]→L[ℝ] ℝ) :
    |Library.Geometry.Manifold.StokesIntegralDefs.topCoeff α| ≤ ‖α‖ := by
  simp only [topCoeff]
  have hle := ContinuousAlternatingMap.le_opNorm α (EuclideanSpace.basisFun (Fin d) ℝ)
  simp only [Real.norm_eq_abs] at hle
  have hprod : ∏ i : Fin d, ‖(EuclideanSpace.basisFun (Fin d) ℝ) i‖ = 1 := by
    apply Finset.prod_eq_one
    intro i _
    exact (EuclideanSpace.basisFun (Fin d) ℝ).orthonormal.1 i
  rw [hprod, mul_one] at hle
  exact hle

/-- Pointwise coordinate bound for the flat pullback's local coefficient.

`localCoeff = topCoeff (formInCoord …)` by definitional equality; `coord_rep_pullback`
rewrites `formInCoord` to `(ψ …).compContinuousLinearMap (fderivWithin …)`. Then
`topcoeff_le_norm` gives `|topCoeff β| ≤ ‖β‖`, and
`ContinuousAlternatingMap.norm_compContinuousLinearMap_le` gives
`‖β‖ ≤ ‖ψ …‖ · ‖fderivWithin …‖ ^ (n + 1)` (using `Fintype.card_fin`),
while `hM` provides the scaling `‖ψ …‖ ≤ M`. -/
theorem pullback_pointwise_coord_bound
    {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e)
    (ψ : F → (F [⋀^Fin (n + 1)]→L[ℝ] ℝ)) (hψ : ContDiff ℝ ∞ ψ) (M : ℝ)
    (hM : ∀ y, ‖ψ y‖ ≤ M)
    (x : N) (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hy : y ∈ (extChartAt (𝓡∂ (n + 1)) x).target) :
    |localCoeff (pullbackFlatForm e ψ he hψ) x y| ≤
      M * ‖fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x).symm)
        (Set.range (𝓡∂ (n + 1))) y‖ ^ (n + 1) := by
  have hrep : formInCoord (𝓡∂ (n + 1)) (pullbackFlatForm e ψ he hψ) x y
      = (ψ (e ((extChartAt (𝓡∂ (n + 1)) x).symm y))).compContinuousLinearMap
          (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x).symm)
            (Set.range (𝓡∂ (n + 1))) y) :=
    coord_rep_pullback e ψ he hψ x y hy
  have htop : |topCoeff ((ψ (e ((extChartAt (𝓡∂ (n + 1)) x).symm y))).compContinuousLinearMap
          (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x).symm)
            (Set.range (𝓡∂ (n + 1))) y))|
      ≤ ‖(ψ (e ((extChartAt (𝓡∂ (n + 1)) x).symm y))).compContinuousLinearMap
          (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x).symm)
            (Set.range (𝓡∂ (n + 1))) y)‖ := topcoeff_le_norm _
  have hcomp := ContinuousAlternatingMap.norm_compContinuousLinearMap_le
      (ψ (e ((extChartAt (𝓡∂ (n + 1)) x).symm y)))
      (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x).symm)
        (Set.range (𝓡∂ (n + 1))) y)
  have hMy := hM (e ((extChartAt (𝓡∂ (n + 1)) x).symm y))
  rw [show localCoeff (pullbackFlatForm e ψ he hψ) x y
      = topCoeff (formInCoord (𝓡∂ (n + 1)) (pullbackFlatForm e ψ he hψ) x y) from rfl, hrep]
  calc |topCoeff ((ψ (e ((extChartAt (𝓡∂ (n + 1)) x).symm y))).compContinuousLinearMap
            (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x).symm)
              (Set.range (𝓡∂ (n + 1))) y))|
        ≤ ‖(ψ (e ((extChartAt (𝓡∂ (n + 1)) x).symm y))).compContinuousLinearMap
            (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x).symm)
              (Set.range (𝓡∂ (n + 1))) y)‖ := htop
    _ ≤ ‖ψ (e ((extChartAt (𝓡∂ (n + 1)) x).symm y))‖
          * ‖fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x).symm)
              (Set.range (𝓡∂ (n + 1))) y‖ ^ Fintype.card (Fin (n + 1)) := hcomp
    _ = ‖ψ (e ((extChartAt (𝓡∂ (n + 1)) x).symm y))‖
          * ‖fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x).symm)
              (Set.range (𝓡∂ (n + 1))) y‖ ^ (n + 1) := by rw [Fintype.card_fin]
    _ ≤ M * ‖fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x).symm)
              (Set.range (𝓡∂ (n + 1))) y‖ ^ (n + 1) :=
      mul_le_mul_of_nonneg_right hMy (by positivity)

/-- Restricts the chart-target integral to the chart image of the POU's tsupport.

The integrand vanishes off the image `extChartAt '' tsupport (POU i)`, so
`MeasureTheory.setIntegral_eq_of_subset_of_forall_diff_eq_zero` applies:
(a) the chart target is measurable (open preimage intersected with a closed range),
(b) the image is contained in the target via `tsupport_subset_extChartAt_source` and
`map_source`, and (c) the integrand vanishes on the difference — if the POU factor were
nonzero at some `y` outside the image, then `pou_nonzero_point_in_image` would place `y`
inside the image, a contradiction. -/
theorem chart_integral_restrict
    {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
    {ι : Type*} (B : SmoothBumpCovering ι (𝓡∂ (n + 1)) N Set.univ) (i : ι)
    (φ : DiffForm (𝓡∂ (n + 1)) N (n + 1)) :
    ∫ y in (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
        B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y)
          * localCoeff φ (B.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := N)) (B.c i) y)
          ∂MeasureTheory.volume
      = ∫ y in (extChartAt (𝓡∂ (n + 1)) (B.c i)) '' tsupport (B.toSmoothPartitionOfUnity i),
        B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y)
          * localCoeff φ (B.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := N)) (B.c i) y)
          ∂MeasureTheory.volume := by
  have htmeas : MeasurableSet (extChartAt (𝓡∂ (n + 1)) (B.c i)).target := by
    rw [extChartAt_target]
    exact ((chartAt (EuclideanHalfSpace (n + 1)) (B.c i)).open_target.preimage
      (𝓡∂ (n + 1)).continuous_symm).measurableSet.inter
      (𝓡∂ (n + 1)).isClosed_range.measurableSet
  have hsupp_sub : tsupport (B.toSmoothPartitionOfUnity i) ⊆
      (extChartAt (𝓡∂ (n + 1)) (B.c i)).source :=
    (closure_mono (SmoothBumpCovering.support_toSmoothPartitionOfUnity_subset B i)).trans
      (B i).tsupport_subset_extChartAt_source
  have hsub : (extChartAt (𝓡∂ (n + 1)) (B.c i)) '' tsupport (B.toSmoothPartitionOfUnity i)
      ⊆ (extChartAt (𝓡∂ (n + 1)) (B.c i)).target := by
    rw [Set.image_subset_iff]
    intro x hx
    exact (extChartAt (𝓡∂ (n + 1)) (B.c i)).map_source (hsupp_sub hx)
  apply MeasureTheory.setIntegral_eq_of_subset_of_forall_diff_eq_zero htmeas hsub
  intro y hy
  have hpou : B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y) = 0 := by
    by_contra h
    exact hy.2 (pou_nonzero_point_in_image B i y hy.1 h)
  rw [hpou]
  ring

/-- The chart image of a POU bump's tsupport has finite volume.

`tsupport (POU i) ⊆ tsupport (B i)` by `closure_mono`; the latter is compact by
`HasCompactSupport.isCompact`. The restriction is therefore a compact subset of the chart
source, whose `extChartAt` image is compact via `IsCompact.image_of_continuousOn` with
`continuousOn_extChartAt`, and hence has finite measure by `IsCompact.measure_lt_top`. -/
theorem image_volume_lt_top
    {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
    {ι : Type*} (B : SmoothBumpCovering ι (𝓡∂ (n + 1)) N Set.univ) (i : ι) :
    MeasureTheory.volume ((extChartAt (𝓡∂ (n + 1)) (B.c i)) ''
        tsupport (B.toSmoothPartitionOfUnity i)) < ⊤ := by
  have hsupp_sub : tsupport (B.toSmoothPartitionOfUnity i) ⊆ tsupport (B i) :=
    closure_mono (SmoothBumpCovering.support_toSmoothPartitionOfUnity_subset B i)
  have hcomp : IsCompact (tsupport (B i)) := (B i).hasCompactSupport.isCompact
  have hcomp_sub : IsCompact (tsupport (B.toSmoothPartitionOfUnity i)) :=
    hcomp.of_isClosed_subset (isClosed_tsupport _) hsupp_sub
  have hsource : tsupport (B.toSmoothPartitionOfUnity i) ⊆
      (extChartAt (𝓡∂ (n + 1)) (B.c i)).source :=
    hsupp_sub.trans (B i).tsupport_subset_extChartAt_source
  have himg : IsCompact ((extChartAt (𝓡∂ (n + 1)) (B.c i)) ''
      (tsupport (B.toSmoothPartitionOfUnity i))) :=
    hcomp_sub.image_of_continuousOn ((continuousOn_extChartAt (B.c i)).mono hsource)
  exact himg.measure_lt_top

/-- The `extChartAt`-image of the tsupport of partition-of-unity piece `i` is contained in
the chart target, via `support_toSmoothPartitionOfUnity_subset`,
`tsupport_subset_extChartAt_source`, and `PartialEquiv.image_source_eq_target`. -/
theorem image_subset_target
    {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {ι : Type*} (B : SmoothBumpCovering ι (𝓡∂ (n + 1)) N Set.univ) (i : ι) :
    (extChartAt (𝓡∂ (n + 1)) (B.c i)) '' tsupport (B.toSmoothPartitionOfUnity i) ⊆
      (extChartAt (𝓡∂ (n + 1)) (B.c i)).target := by
  have hts : tsupport (B.toSmoothPartitionOfUnity i) ⊆
      (extChartAt (𝓡∂ (n + 1)) (B.c i)).source :=
    (closure_mono (B.support_toSmoothPartitionOfUnity_subset i)).trans
      (B i).tsupport_subset_extChartAt_source
  calc (extChartAt (𝓡∂ (n + 1)) (B.c i)) '' tsupport (B.toSmoothPartitionOfUnity i)
      ⊆ (extChartAt (𝓡∂ (n + 1)) (B.c i)) '' (extChartAt (𝓡∂ (n + 1)) (B.c i)).source :=
        Set.image_mono hts
    _ = (extChartAt (𝓡∂ (n + 1)) (B.c i)).target :=
        PartialEquiv.image_source_eq_target _

/-- Pointwise bound `‖POU_i · localCoeff · sign‖ ≤ K` on the chart integrand over the image
of `tsupport POU_i`.

Reduces to the abstract real-arithmetic lemma `prod_norm_le` (`0 ≤ a ≤ 1`,
`a ≠ 0 → |b| ≤ K`, `c ∈ {-1, 0, 1}` ⇒ `‖a · b · c‖ ≤ K`), fed by the POU factor
bounds (`SmoothPartitionOfUnity.nonneg`/`.le_one`), `Real.sign_apply_eq` for the sign
factor, and `hlc` for `|localCoeff| ≤ K`. The latter requires `y` in the chart target,
supplied by `image_subset_target`. -/
theorem integrand_norm_le_on_image
    {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
    {ι : Type*} (B : SmoothBumpCovering ι (𝓡∂ (n + 1)) N Set.univ) (i : ι)
    (φ : DiffForm (𝓡∂ (n + 1)) N (n + 1)) (K : ℝ) (hK : 0 ≤ K)
    (hlc : ∀ y ∈ (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
        B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y) ≠ 0 →
        |localCoeff φ (B.c i) y| ≤ K) :
    ∀ y ∈ (extChartAt (𝓡∂ (n + 1)) (B.c i)) '' tsupport (B.toSmoothPartitionOfUnity i),
      ‖B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y)
          * localCoeff φ (B.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := N))
              (B.c i) y)‖ ≤ K := by
  intro y hy
  exact prod_norm_le _ _ _ K
    (B.toSmoothPartitionOfUnity.nonneg i _)
    (B.toSmoothPartitionOfUnity.le_one i _)
    (fun hne => hlc y (image_subset_target B i hy) hne)
    (Real.sign_apply_eq _) hK

/-- Per-chart integral bound: `|∫ POU_i · localCoeff · sign| ≤ K · vol(image of tsupport)`.

The integrand vanishes off `S := extChartAt '' tsupport POU_i`, so the chart-target
integral restricts to `S` via `chart_integral_restrict`; on `S` the integrand has norm
≤ K by `integrand_norm_le_on_image` (POU_i ∈ [0, 1], |sign| ≤ 1, |localCoeff| ≤ K from
`hlc`); and `S` has finite volume by `image_volume_lt_top` (continuous image of a compact
tsupport). Then `MeasureTheory.norm_setIntegral_le_of_norm_le_const` gives the bound. -/
theorem chart_term_bound
    {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
    {ι : Type*} (B : SmoothBumpCovering ι (𝓡∂ (n + 1)) N Set.univ) (i : ι)
    (φ : DiffForm (𝓡∂ (n + 1)) N (n + 1)) (K : ℝ) (hK : 0 ≤ K)
    (hlc : ∀ y ∈ (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
        B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y) ≠ 0 →
        |localCoeff φ (B.c i) y| ≤ K) :
    |∫ y in (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
        B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y)
          * localCoeff φ (B.c i) y
          * Real.sign (localCoeff (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := N)) (B.c i) y)
          ∂MeasureTheory.volume|
      ≤ K * (MeasureTheory.volume ((extChartAt (𝓡∂ (n + 1)) (B.c i)) ''
          tsupport (B.toSmoothPartitionOfUnity i))).toReal := by
  have hrestrict :
      ∫ y in (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
          B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y)
            * localCoeff φ (B.c i) y
            * Real.sign (localCoeff (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := N)) (B.c i) y)
            ∂MeasureTheory.volume
        = ∫ y in (extChartAt (𝓡∂ (n + 1)) (B.c i)) '' tsupport (B.toSmoothPartitionOfUnity i),
          B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y)
            * localCoeff φ (B.c i) y
            * Real.sign (localCoeff (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := N)) (B.c i) y)
            ∂MeasureTheory.volume := chart_integral_restrict B i φ
  have hbound : ∀ y ∈ (extChartAt (𝓡∂ (n + 1)) (B.c i)) ''
      tsupport (B.toSmoothPartitionOfUnity i),
      ‖B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y)
            * localCoeff φ (B.c i) y
            * Real.sign (localCoeff (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := N))
                (B.c i) y)‖ ≤ K := integrand_norm_le_on_image B i φ K hK hlc
  have hvol : MeasureTheory.volume ((extChartAt (𝓡∂ (n + 1)) (B.c i)) ''
      tsupport (B.toSmoothPartitionOfUnity i)) < ⊤ := image_volume_lt_top B i
  rw [hrestrict]
  have hmain := MeasureTheory.norm_setIntegral_le_of_norm_le_const hvol hbound
  simpa [Real.norm_eq_abs, MeasureTheory.Measure.real] using hmain

/-- Assembles the `C * M` integral bound from a finite subordinate smooth bump covering `B`.

`integral_eq_finsum_over_subordinate` rewrites the integral as a `∑ᶠ` over `B`; each
chart term is bounded by `chart_term_bound` with `K = M * D`, where the per-point
`localCoeff` bound comes from `pullback_pointwise_coord_bound` composed with the
chart-derivative bound `hD`; and `finsum_abs_le` sums the finitely-many bounded terms.
The witness is `C = (∑ᶠ i, vol (extChartAt (B.c i) '' tsupport (POU i))) * D ≥ 0`. -/
theorem finsum_assembly
    {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e)
    {ι : Type*} (B : SmoothBumpCovering ι (𝓡∂ (n + 1)) N Set.univ)
    (hB : B.IsSubordinate (fun x ↦ (chartAt (EuclideanHalfSpace (n + 1)) x).source))
    (D : ℝ) (hD0 : 0 ≤ D)
    (hD : ∀ (i : ι),
      ∀ y ∈ (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
        B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y) ≠ 0 →
        ‖fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) (B.c i)).symm)
          (Set.range (𝓡∂ (n + 1))) y‖ ^ (n + 1) ≤ D) :
    ∃ C : ℝ, 0 ≤ C ∧ ∀ (ψ : F → (F [⋀^Fin (n + 1)]→L[ℝ] ℝ))
      (hψ : ContDiff ℝ ∞ ψ) (M : ℝ), (∀ y, ‖ψ y‖ ≤ M) →
      |DiffForm.integral (pullbackFlatForm e ψ he hψ)| ≤ C * M := by
  classical
  haveI : Fintype ι := B.fintype
  refine ⟨(∑ᶠ i, (MeasureTheory.volume ((extChartAt (𝓡∂ (n + 1)) (B.c i)) ''
      tsupport (B.toSmoothPartitionOfUnity i))).toReal) * D, ?_, ?_⟩
  · exact mul_nonneg (finsum_nonneg fun i => ENNReal.toReal_nonneg) hD0
  · intro ψ hψ M hM
    have hM0 : 0 ≤ M := le_trans (norm_nonneg _) (hM 0)
    rw [Library.Geometry.Manifold.IntegralEquivFinsum.integral_eq_finsum_over_subordinate
      (pullbackFlatForm e ψ he hψ) B hB]
    have hterm : ∀ i,
        |∫ y in (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
            B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y)
              * localCoeff (pullbackFlatForm e ψ he hψ) (B.c i) y
              * Real.sign
                  (localCoeff (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := N)) (B.c i) y)
              ∂MeasureTheory.volume|
          ≤ (M * D) * (MeasureTheory.volume ((extChartAt (𝓡∂ (n + 1)) (B.c i)) ''
              tsupport (B.toSmoothPartitionOfUnity i))).toReal := by
      intro i
      apply chart_term_bound B i (pullbackFlatForm e ψ he hψ) (M * D) (mul_nonneg hM0 hD0)
      intro y hy hne
      exact le_trans (pullback_pointwise_coord_bound e he ψ hψ M hM (B.c i) y hy)
        (mul_le_mul_of_nonneg_left (hD i y hy hne) hM0)
    refine le_trans (finsum_abs_le _ _ (M * D) (fun i => ENNReal.toReal_nonneg) hterm) ?_
    exact le_of_eq (by ring)

/-- **Integral bound for `pullbackFlatForm`**: for any compact manifold-with-boundary `N`
and smooth map `e : N → F`, there exists `C ≥ 0` such that for every smooth family
`ψ : F → (F [⋀^Fin (n + 1)]→L[ℝ] ℝ)` with uniform bound `‖ψ y‖ ≤ M`, we have
`|DiffForm.integral (pullbackFlatForm e ψ he hψ)| ≤ C * M`.

The proof chooses a subordinate smooth bump covering `B` via
`SmoothBumpCovering.exists_isSubordinate`, extracts a uniform chart-derivative bound `D`
via `finite_cover_deriv_bound`, and applies `finsum_assembly`. -/
theorem pullbackFlatForm_integral_bounded : ∀ {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e),
    ∃ C : ℝ, 0 ≤ C ∧ ∀ (ψ : F → (F [⋀^Fin (n + 1)]→L[ℝ] ℝ))
      (hψ : ContDiff ℝ ∞ ψ) (M : ℝ), (∀ y, ‖ψ y‖ ≤ M) →
      |DiffForm.integral (pullbackFlatForm e ψ he hψ)| ≤ C * M := by
  intro n N _ _ _ _ _ _ F _ _ e he
  obtain ⟨ι, B, hB⟩ := SmoothBumpCovering.exists_isSubordinate
    (I := 𝓡∂ (n + 1)) (M := N) (s := (Set.univ : Set N))
    (U := fun x ↦ (chartAt (EuclideanHalfSpace (n + 1)) x).source)
    isClosed_univ
    (fun x _ ↦ (chartAt (EuclideanHalfSpace (n + 1)) x).open_source.mem_nhds
      (mem_chart_source _ x))
  obtain ⟨D, hD0, hD⟩ := finite_cover_deriv_bound e he B hB
  exact finsum_assembly e he B hB D hD0 hD

end Library.Geometry.Currents.PullbackFormBounded
