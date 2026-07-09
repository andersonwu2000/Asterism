import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.InducedOrientNonzero         -- inducedOrient, inducedOrient_ne_zero
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBdry.PullbackBdryDefs         -- pullbackBdryFun
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff    -- contMDiff_pullbackBdryFun
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.Normed.Module.Alternating.Basic
import Mathlib.Data.Real.Sign
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.LinearAlgebra.Orientation
import Mathlib.MeasureTheory.Constructions.BorelSpace.Basic
import Mathlib.MeasureTheory.Integral.Bochner.Basic
import Mathlib.MeasureTheory.Integral.Bochner.Set
import Mathlib.Topology.Compactness.Compact
import Mathlib.Topology.Connected.Basic
import Mathlib.Topology.Hom.ContinuousEvalConst
import Mathlib.Topology.Separation.Basic

/-!
# Sign of the reference form's local coefficient

This file establishes that the local coefficient of the reference orientation form of an oriented
manifold has constant sign on any preconnected subset of a chart target. It also provides a
lemma factoring a pointwise-constant sign out of a set integral.

## Main statements

- `sign_const_of_continuousOn_ne_zero_preconnected`: a continuous, nowhere-zero real function on
  a preconnected set has constant sign in `{1, -1}`.
- `refform_localcoeff_ne_zero_target`: the local coefficient of the reference form is nonzero
  on the chart target.
- `refform_localcoeff_continuousOn_target`: the local coefficient of the reference form is
  continuous on the chart target.
- `sign_localcoeff_refform_const_on_preconnected`: the sign of the local coefficient of the
  reference form is constant on any preconnected subset of the chart target.
- `sign_const_factor_localcoeff`: a pointwise-constant orientation sign factors out of a set
  integral over the chart target.
-/

open Bundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.InducedOrientNonzero
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open MeasureTheory
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.RefFormSign

/-- A continuous, nowhere-zero real function on a preconnected set has constant sign equal to
either `1` or `-1`. -/
theorem sign_const_of_continuousOn_ne_zero_preconnected
    {X : Type*} [TopologicalSpace X] (f : X → ℝ) (s : Set X)
    (hcont : ContinuousOn f s) (hne : ∀ y ∈ s, f y ≠ 0)
    (hconn : IsPreconnected s) :
    ∃ eps : ℝ, (eps = 1 ∨ eps = -1) ∧ ∀ y ∈ s, Real.sign (f y) = eps := by
  rcases hconn.mapsTo_Ioi_or_Iio hcont hne with h | h
  · exact ⟨1, Or.inl rfl, fun y hy => Real.sign_of_pos (h hy)⟩
  · exact ⟨-1, Or.inr rfl, fun y hy => Real.sign_of_neg (h hy)⟩

/-- A nonzero top-degree continuous alternating form on Euclidean space has nonzero top
coefficient (its value on the standard basis). -/
theorem topcoeff_ne_zero_of_form_ne_zero
    {d : ℕ}
    (α : EuclideanSpace ℝ (Fin d) [⋀^Fin d]→L[ℝ] ℝ) (hα : α ≠ 0) :
    topCoeff α ≠ 0 := by
  have hα' : α.toAlternatingMap ≠ 0 := fun h =>
    hα (ContinuousAlternatingMap.toAlternatingMap_injective (by simpa using h))
  have key : α.toAlternatingMap (EuclideanSpace.basisFun (Fin d) ℝ).toBasis ≠ 0 :=
    (AlternatingMap.map_basis_ne_zero_iff (EuclideanSpace.basisFun (Fin d) ℝ).toBasis
      α.toAlternatingMap).mpr hα'
  simpa [topCoeff, ContinuousAlternatingMap.coe_toAlternatingMap,
    OrthonormalBasis.coe_toBasis] using key

/-- For an oriented manifold, `formInCoord` applied to the reference form is nonzero at every
point of the chart target. -/
theorem refform_formincoord_ne_zero_target
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [OrientedManifold I N]
    (c₀ : N) :
    ∀ y ∈ (extChartAt I c₀).target,
      formInCoord I (OrientedManifold.refForm (I := I) (N := N)) c₀ y ≠ 0 := by
  have h_cc_ne : ∀ (k : ℕ) (i j : atlas EH N) (x : N),
      x ∈ (tangentBundleCore I N).baseSet i → x ∈ (tangentBundleCore I N).baseSet j →
      ∀ (v : EuclideanSpace ℝ (Fin d) [⋀^Fin k]→L[ℝ] ℝ), v ≠ 0 →
        Library.Geometry.Manifold.FormCoordChange.formCoordChange I k i j x v ≠ 0 := by
    intro k i j x hi hj v hv hcontra
    apply hv
    have hcomp := Library.Geometry.Manifold.FormCoordChange.formCoordChange_comp
      I k i j i x ⟨⟨hi, hj⟩, hi⟩ v
    rw [hcontra, map_zero] at hcomp
    rw [Library.Geometry.Manifold.FormCoordChangeSelf.formCoordChange_self I k i x hi v] at hcomp
    exact hcomp.symm
  intro y hy
  have hp_src : (extChartAt I c₀).symm y ∈ (extChartAt I c₀).source :=
    (extChartAt I c₀).map_target hy
  have hp : (extChartAt I c₀).symm y ∈ (chartAt EH c₀).source := by
    simpa only [extChartAt_source] using hp_src
  have hy_eq : extChartAt I c₀ ((extChartAt I c₀).symm y) = y :=
    (extChartAt I c₀).right_inv hy
  rw [← hy_eq, form_in_coord_eq_coord_change I
    (OrientedManifold.refForm (I := I) (N := N)) c₀ hp]
  exact h_cc_ne d (achart EH ((extChartAt I c₀).symm y)) (achart EH c₀)
    ((extChartAt I c₀).symm y) (mem_chart_source EH _) hp
    (OrientedManifold.refForm (I := I) (N := N) ((extChartAt I c₀).symm y))
    (OrientedManifold.refForm_ne _)

/-- The local coefficient of the reference form is nonzero at every point of the chart target. -/
theorem refform_localcoeff_ne_zero_target
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [OrientedManifold I N]
    (c₀ : N) :
    ∀ y ∈ (extChartAt I c₀).target,
      localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y ≠ 0 := by
  intro y hy
  have hA := refform_formincoord_ne_zero_target (I := I) (N := N) c₀ y hy
  exact topcoeff_ne_zero_of_form_ne_zero _ hA

/-- The local coefficient of the reference form is continuous on the chart target. -/
theorem refform_localcoeff_continuousOn_target
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [OrientedManifold I N]
    (c₀ : N) :
    ContinuousOn
      (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀)
      (extChartAt I c₀).target := by
  unfold localCoeff topCoeff
  have hf := (Library.Geometry.Manifold.MExtDerivCoord.form_in_coord_smooth I
    OrientedManifold.refForm c₀).continuousOn
  exact (continuous_eval_const _).comp_continuousOn hf

/-- The sign of the local coefficient of the reference form is constant on any preconnected
subset of the chart target. -/
theorem sign_localcoeff_refform_const_on_preconnected
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [OrientedManifold I N]
    (c₀ : N) (s : Set (EuclideanSpace ℝ (Fin d)))
    (hs : IsPreconnected s) (hsub : s ⊆ (extChartAt I c₀).target) :
    ∃ eps : ℝ, (eps = 1 ∨ eps = -1) ∧
      ∀ y ∈ s,
        Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y) = eps := by
  have hcont := refform_localcoeff_continuousOn_target (I := I) (N := N) c₀
  have hne := refform_localcoeff_ne_zero_target (I := I) (N := N) c₀
  exact sign_const_of_continuousOn_ne_zero_preconnected
    (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀) s
    (hcont.mono hsub) (fun y hy => hne y (hsub hy)) hs

/-- When the sign of `localCoeff (refForm) c₀` equals a constant `eps` wherever
`localCoeff w c₀` is nonzero, that sign factors out of the set integral as a scalar multiple. -/
theorem sign_const_factor_localcoeff
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N]
    (w : DiffForm I N d) (c₀ : N) (eps : ℝ)
    (hconst : ∀ y ∈ (extChartAt I c₀).target,
        localCoeff w c₀ y ≠ 0 →
        Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y) = eps) :
    (∫ y in (extChartAt I c₀).target,
        Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) c₀ y)
          * localCoeff w c₀ y ∂MeasureTheory.volume)
      = eps • ∫ y in (extChartAt I c₀).target,
          localCoeff w c₀ y ∂MeasureTheory.volume := by
  have hT : MeasurableSet (extChartAt I c₀).target := by
    rw [extChartAt_target]
    exact ((chartAt EH c₀).open_target.preimage I.continuous_symm).measurableSet.inter
      I.isClosed_range.measurableSet
  rw [smul_eq_mul, ← integral_const_mul]
  apply setIntegral_congr_fun hT
  intro y hy
  by_cases hw : localCoeff w c₀ y = 0
  · simp [hw]
  · dsimp only; rw [hconst y hy hw]

end Library.Geometry.Manifold.RefFormSign
