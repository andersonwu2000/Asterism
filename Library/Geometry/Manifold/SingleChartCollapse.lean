import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.InducedOrientNonzero         -- inducedOrient, inducedOrient_ne_zero
import Library.Geometry.Manifold.IntegralEquivFinsum
import Library.Geometry.Manifold.PouDensityCollapse
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBdry.PullbackBdryDefs         -- pullbackBdryFun
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff    -- contMDiff_pullbackBdryFun
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry
import Mathlib.Algebra.BigOperators.Finprod
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.NormedSpace.Multilinear.Basic
import Mathlib.Data.Real.Sign
import Mathlib.Data.Set.Finite.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.PartitionOfUnity
import Mathlib.MeasureTheory.Integral.Bochner.Basic
import Mathlib.MeasureTheory.Integral.Bochner.Set
import Mathlib.MeasureTheory.Measure.MeasureSpace
import Mathlib.Topology.Algebra.Support
import Mathlib.Topology.Compactness.Compact
import Mathlib.Topology.LocallyFinite
import Mathlib.Topology.Separation.Hausdorff

/-!
# Single-chart collapse for manifold integrals

This file shows that the `DiffForm.integral` of a top-degree form whose support lies in
a single chart can be expressed as a single Lebesgue integral over that chart's target,
and establishes the additivity of the covering-based integral representation.

## Main statements

- `localCoeff_add`: `localCoeff` is additive in the form argument.
- `integral_term_support_finite`: the support of the per-chart integrand family is finite.
- `per_chart_integral_add`: per-chart additivity of the signed PoU-weighted chart integral.
- `integral_add_over_covering`: additivity of the covering integral over a `SmoothBumpCovering`.
- `integral_single_chart_collapse`: a form supported in one chart integrates via that chart.
-/

open Bundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.InducedOrientNonzero
open Library.Geometry.Manifold.IntegralEquivFinsum
open Library.Geometry.Manifold.PouDensityCollapse
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open MeasureTheory
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.SingleChartCollapse

variable {d : ℕ} {EH : Type*} [TopologicalSpace EH]
  {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
  {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
  [IsManifold I ∞ N] [CompactSpace N]

/-- `localCoeff` is additive in the form argument: the local coordinate representative
of a sum equals the sum of the local coordinate representatives. -/
theorem localCoeff_add
    (φ ψ : DiffForm I N d) (x : N) (y : EuclideanSpace ℝ (Fin d)) :
    localCoeff (φ + ψ) x y = localCoeff φ x y + localCoeff ψ x y := by
  simp only [localCoeff, topCoeff, Library.Geometry.Manifold.MExtDerivCoord.formInCoord]
  rw [show (φ + ψ) ((extChartAt I x).symm y) = φ ((extChartAt I x).symm y) +
      ψ ((extChartAt I x).symm y) from rfl]
  rw [map_add]
  simp [ContinuousAlternatingMap.add_apply]

/-- The support of the family `i ↦ ∫ (PoUᵢ · localCoeff φ · sign) dVol` is finite.
This follows from local finiteness of the partition-of-unity supports together with
compactness of `N`. -/
theorem integral_term_support_finite [OrientedManifold I N]
    (φ : DiffForm I N d)
    {ιM : Type*} (B : SmoothBumpCovering ιM I N)
    (_hB : B.IsSubordinate fun x => (chartAt EH x).source) :
    (Function.support fun i =>
        ∫ y in (extChartAt I (B.c i)).target,
          B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff φ (B.c i) y
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
            ∂volume).Finite := by
  apply Set.Finite.subset
    (B.toSmoothPartitionOfUnity.locallyFinite.finite_nonempty_of_compact)
  intro i hi
  simp only [Function.mem_support] at hi
  rw [Set.mem_setOf_eq, Set.nonempty_iff_ne_empty, Ne, Function.support_eq_empty_iff]
  intro hzero
  apply hi
  have hz : B.toSmoothPartitionOfUnity i = 0 := by ext x; exact congrFun hzero x
  simp [hz]

/-- Per-chart additivity of the signed, PoU-weighted chart integral:
the integral of `PoUᵢ · localCoeff (a + b) · sign` equals the sum of the
corresponding integrals for `a` and `b` separately. -/
theorem per_chart_integral_add [OrientedManifold I N]
    (a b : DiffForm I N d)
    {ιM : Type*} (B : SmoothBumpCovering ιM I N)
    (_hB : B.IsSubordinate fun x => (chartAt EH x).source) :
    ∀ i,
      (∫ y in (extChartAt I (B.c i)).target,
          B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff (a + b) (B.c i) y
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
            ∂volume) =
      (∫ y in (extChartAt I (B.c i)).target,
          B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff a (B.c i) y
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
            ∂volume) +
      (∫ y in (extChartAt I (B.c i)).target,
          B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff b (B.c i) y
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
            ∂volume) := by
  intro i
  have hia := weighted_signed_integrand_integrable a B i
  have hib := weighted_signed_integrand_integrable b B i
  have hadd := localCoeff_add a b
  have key :
      (∫ y in (extChartAt I (B.c i)).target,
          B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff (a + b) (B.c i) y
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
            ∂volume) =
      ∫ y in (extChartAt I (B.c i)).target,
        (B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff a (B.c i) y
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y) +
          B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff b (B.c i) y
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y))
        ∂volume := by
    congr 1
    funext y
    rw [hadd]
    ring
  rw [key, integral_add hia hib]

/-- Additivity of the de-sealed covering integral over a `SmoothBumpCovering`:
the `∑ᶠ`-integral of `a + b` equals the sum of the `∑ᶠ`-integrals of `a` and `b`. -/
theorem integral_add_over_covering [OrientedManifold I N]
    (a b : DiffForm I N d)
    {ιM : Type*} (B : SmoothBumpCovering ιM I N)
    (hB : B.IsSubordinate fun x => (chartAt EH x).source) :
    (∑ᶠ i,
        ∫ y in (extChartAt I (B.c i)).target,
          B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff (a + b) (B.c i) y
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
            ∂volume) =
    (∑ᶠ i,
        ∫ y in (extChartAt I (B.c i)).target,
          B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff a (B.c i) y
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
            ∂volume) +
    (∑ᶠ i,
        ∫ y in (extChartAt I (B.c i)).target,
          B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
            * localCoeff b (B.c i) y
            * Real.sign
                (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B.c i) y)
            ∂volume) := by
  have hper := per_chart_integral_add a b B hB
  have hsa := integral_term_support_finite a B hB
  have hsb := integral_term_support_finite b B hB
  rw [finsum_congr hper]
  exact finsum_add_distrib hsa hsb

/-- A top-degree form supported in a single chart integrates via that chart:
if `tsupport (fun x => g x) ⊆ (chartAt EH c₀).source`, then the signed chart integral
over the target of `extChartAt I c₀` equals `DiffForm.integral g`. -/
theorem integral_single_chart_collapse [OrientedManifold I N]
    (g : DiffForm I N d) (c₀ : N)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt EH c₀).source) :
    (∫ y in (extChartAt I c₀).target,
        Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y)
          * localCoeff g c₀ y
          ∂MeasureTheory.volume) = DiffForm.integral g := by
  obtain ⟨ι, B, hB⟩ :=
    SmoothBumpCovering.exists_isSubordinate (I := I) (M := N)
      (s := (Set.univ : Set N)) isClosed_univ
      (U := fun x => (chartAt EH x).source)
      (fun x _ => (chartAt EH x).open_source.mem_nhds (mem_chart_source _ x))
  have h1 := integral_eq_finsum_over_subordinate g B hB
  have h2 := per_chart_density_to_c0 g c₀ hsupp B.toSmoothPartitionOfUnity B.c
    hB.toSmoothPartitionOfUnity
  have h3 := finsum_pou_density_collapse_hsupp g c₀ hsupp B.toSmoothPartitionOfUnity B.c
    hB.toSmoothPartitionOfUnity
  exact (h1.trans ((finsum_congr h2).trans h3)).symm

end Library.Geometry.Manifold.SingleChartCollapse
