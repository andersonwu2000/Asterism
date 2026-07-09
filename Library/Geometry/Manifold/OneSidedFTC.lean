import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.InducedOrientNonzero         -- inducedOrient, inducedOrient_ne_zero
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBdry.PullbackBdryDefs         -- pullbackBdryFun
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff    -- contMDiff_pullbackBdryFun
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.Calculus.Deriv.Basic
import Mathlib.Analysis.Calculus.Deriv.Support
import Mathlib.Analysis.Calculus.FDeriv.Basic
import Mathlib.Analysis.Calculus.TangentCone.Real
import Mathlib.MeasureTheory.Function.LocallyIntegrable
import Mathlib.MeasureTheory.Integral.IntegrableOn
import Mathlib.MeasureTheory.Integral.IntegralEqImproper
import Mathlib.Order.Filter.Basic
import Mathlib.Order.Interval.Set.Basic
import Mathlib.Topology.Algebra.Support
import Mathlib.Topology.ContinuousMap.CompactlySupported
import Mathlib.Topology.Order.Compact

/-!
# One-sided Fundamental Theorem of Calculus on ℝ

This file establishes the one-sided FTC for smooth functions with compact support on
half-lines, and the vanishing of the integral of the derivative of a compactly supported
smooth function over all of ℝ.

## Main statements

- `(`:.is_zero_at_infty.mono_left atTop_le_cocompact) a compactly supported function tends to zero at `+∞`.
- `one_sided_ftc_compact`: for `f` smooth on `[b, ∞)` with compact support,
  `∫_{(b,∞)} f' = -f b`.
- `integral_deriv_eq_zero_of_hasCompactSupport`: for a $C^1$ function `f` with compact support,
  `∫_ℝ f' = 0`.
-/

open Bundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.InducedOrientNonzero
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open MeasureTheory
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.OneSidedFTC

/-- A function smooth on `[b, ∞)` satisfies `HasDerivAt f (deriv f x) x` for every `x > b`. -/
theorem hasDerivAt_deriv_of_contDiffOn_ioi {f : ℝ → ℝ} {b : ℝ}
    (hf : ContDiffOn ℝ ∞ f (Set.Ici b)) :
    ∀ x ∈ Set.Ioi b, HasDerivAt f (deriv f x) x := by
  intro x hx
  have hmem : Set.Ici b ∈ nhds x :=
    Filter.mem_of_superset (Ioi_mem_nhds hx) Set.Ioi_subset_Ici_self
  exact ((hf.contDiffAt hmem).differentiableAt (by norm_num)).hasDerivAt

/-- If `f` has compact support then `derivWithin f (Set.Ici b)` also has compact support. -/
theorem hasCompactSupport_derivWithin_Ici {f : ℝ → ℝ} {b : ℝ}
    (hsupp : HasCompactSupport f) :
    HasCompactSupport (derivWithin f (Set.Ici b)) := by
  apply hsupp.mono'
  intro x hx
  by_contra h
  have hd : HasDerivWithinAt f 0 (Set.Ici b) x := HasDerivWithinAt.of_notMem_tsupport h
  have hfd0 : HasFDerivWithinAt f (0 : ℝ →L[ℝ] ℝ) (Set.Ici b) x := by
    simp only [HasDerivWithinAt, HasDerivAtFilter,
      ContinuousLinearMap.toSpanSingleton_zero] at hd; exact hd
  have hfdz : fderivWithin ℝ f (Set.Ici b) x = 0 := by simp [fderivWithin, hfd0]
  simp [derivWithin, hfdz, Function.mem_support] at hx

/-- A continuous function on `[c, ∞)` with compact support is integrable on `(c, ∞)`. -/
theorem integrableOn_Ioi_of_continuousOn_Ici_hasCompactSupport {g : ℝ → ℝ} {c : ℝ}
    (hg : ContinuousOn g (Set.Ici c)) (hcs : HasCompactSupport g) :
    MeasureTheory.IntegrableOn g (Set.Ioi c) MeasureTheory.volume := by
  obtain ⟨b, hb⟩ : BddAbove (tsupport g) := hcs.bddAbove
  set b' := max c b
  have hcb' : c ≤ b' := le_max_left _ _
  have h1 : MeasureTheory.IntegrableOn g (Set.Icc c b') MeasureTheory.volume :=
    (hg.mono Set.Icc_subset_Ici_self).integrableOn_Icc
  have hzero : Set.EqOn g 0 (Set.Ioi b') := by
    intro x hx
    apply image_eq_zero_of_notMem_tsupport
    intro hmem
    have hxb : x ≤ b := hb hmem
    have : b < x := lt_of_le_of_lt (le_max_right c b) hx
    exact absurd hxb (not_le.2 this)
  have h2 : MeasureTheory.IntegrableOn g (Set.Ioi b') MeasureTheory.volume :=
    (MeasureTheory.integrableOn_zero).congr_fun hzero.symm measurableSet_Ioi
  have hunion : Set.Ioc c b' ∪ Set.Ioi b' = Set.Ioi c := Set.Ioc_union_Ioi_eq_Ioi hcb'
  have : MeasureTheory.IntegrableOn g (Set.Ioc c b' ∪ Set.Ioi b') MeasureTheory.volume :=
    (h1.mono_set Set.Ioc_subset_Icc_self).union h2
  rwa [hunion] at this

/-- The derivative of a function smooth on `[b, ∞)` with compact support is integrable
on `(b, ∞)`. -/
theorem integrableOn_deriv_Ioi_of_contDiffOn {f : ℝ → ℝ} {b : ℝ}
    (hf : ContDiffOn ℝ ∞ f (Set.Ici b)) (hsupp : HasCompactSupport f) :
    MeasureTheory.IntegrableOn (deriv f) (Set.Ioi b) MeasureTheory.volume := by
  have h_eqon : Set.EqOn (deriv f) (derivWithin f (Set.Ici b)) (Set.Ioi b) :=
    fun x hx => (derivWithin_of_mem_nhds
      (Filter.mem_of_superset (Ioi_mem_nhds hx) Set.Ioi_subset_Ici_self)).symm
  have h_cont : ContinuousOn (derivWithin f (Set.Ici b)) (Set.Ici b) :=
    hf.continuousOn_derivWithin (uniqueDiffOn_Ici b) (by norm_num)
  have h_csupp : HasCompactSupport (derivWithin f (Set.Ici b)) :=
    hasCompactSupport_derivWithin_Ici hsupp
  have h_int : MeasureTheory.IntegrableOn (derivWithin f (Set.Ici b)) (Set.Ioi b)
      MeasureTheory.volume :=
    integrableOn_Ioi_of_continuousOn_Ici_hasCompactSupport h_cont h_csupp
  exact h_int.congr_fun h_eqon.symm measurableSet_Ioi

/-- **One-sided FTC**: if `f` is smooth on `[b, ∞)` with compact support, then
`∫_{(b,∞)} f' = -f b`. -/
theorem one_sided_ftc_compact {f : ℝ → ℝ} {b : ℝ}
    (hf : ContDiffOn ℝ ∞ f (Set.Ici b))
    (hsupp : HasCompactSupport f) :
    (∫ x in Set.Ioi b, deriv f x ∂MeasureTheory.volume) = - f b := by
  have hderiv := hasDerivAt_deriv_of_contDiffOn_ioi hf
  have hcont := (hf.continuousOn b Set.self_mem_Ici)
  have hint := integrableOn_deriv_Ioi_of_contDiffOn hf hsupp
  have htend := (hsupp.is_zero_at_infty.mono_left atTop_le_cocompact)
  have h := MeasureTheory.integral_Ioi_of_hasDerivAt_of_tendsto hcont hderiv hint htend
  simpa using h

/-- For a $C^1$ function with compact support, the integral of its derivative over `ℝ` vanishes. -/
theorem integral_deriv_eq_zero_of_hasCompactSupport
    (f : ℝ → ℝ) (hf : ContDiff ℝ 1 f) (hcs : HasCompactSupport f) :
    ∫ x : ℝ, deriv f x ∂MeasureTheory.volume = 0 := by
  apply MeasureTheory.integral_eq_zero_of_hasDerivAt_of_integrable
  · exact fun x => hf.differentiable one_ne_zero x |>.hasDerivAt
  · exact (hf.continuous_deriv le_rfl).integrable_of_hasCompactSupport hcs.deriv
  · exact hf.continuous.integrable_of_hasCompactSupport hcs

end Library.Geometry.Manifold.OneSidedFTC
