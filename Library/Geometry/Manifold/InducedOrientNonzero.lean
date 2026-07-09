import Library.Geometry.Manifold.DiffFormBundle        -- DiffForm
import Library.Geometry.Manifold.FaceEmbedAlts
import Library.Geometry.Manifold.HalfSpaceNormal
import Library.Geometry.Manifold.InducedOrientDefs       -- inducedOrientFun (P12)
import Library.Geometry.Manifold.InducedOrientSmooth      -- contMDiff_inducedOrientFun (P12)
import Library.Geometry.Manifold.StokesIntegralDefs      -- OrientedManifold (+ refForm)
import Library.Geometry.ManifoldBdry.BdryIsManifold       -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBoundary.CompactBdry      -- Bdry
import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Algebra.Order.Module.Field
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.PartitionOfUnity
import Mathlib.Geometry.Manifold.VectorBundle.Basic
import Mathlib.Topology.Algebra.Module.Alternating.Basic
import Mathlib.Topology.FiberBundle.Basic
import Mathlib.Topology.FiberBundle.Trivialization

/-!
# Nonvanishing of the induced boundary orientation form

This file proves that the induced boundary orientation form `inducedOrient` — built from
`inducedOrientFun` via a partition of unity — is everywhere nonzero on `∂M`. The argument
factors through chart-local nonvanishing of the reference orientation form, injectivity of
trivialization maps, and a positive-ray lemma for POU-weighted sums.

## Main statements

- `formInCoord_refForm_self_ne_zero`: the chart-coordinate read of `refForm` at a self-chart
  image is nonzero.
- `inducedOrientChartFun_self_ne_zero`: `inducedOrientChartFun p p ≠ 0` at every boundary
  point `p`.
- `inducedOrientChartFun_eq_pos_smul_self`: within a shared chart, the `q`-candidate is a
  positive multiple of the anchor `inducedOrientChartFun p p`.
- `sum_smul_ne_zero_of_pos_smul`: a POU-weighted sum of positive multiples of a nonzero anchor
  is nonzero.
- `inducedOrient_ne_zero`: `inducedOrient p ≠ 0` for all `p : Bdry n M`.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.FaceEmbedAlts
open Library.Geometry.Manifold.FormCoordChangeSelf
open Library.Geometry.Manifold.HalfSpaceNormal
open Library.Geometry.Manifold.InducedOrientDefs
open Library.Geometry.Manifold.InducedOrientSmooth
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBoundary.CompactBdry
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.InducedOrientNonzero

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
  [OrientedManifold (𝓡∂ (n + 1)) M]
  [T2Space (Bdry n M)] [SigmaCompactSpace (Bdry n M)]

/-- The induced boundary orientation form `ι_ν μ` on `∂M`, as a genuine smooth `n`-form:
`toFun` is P12's POU-glued `inducedOrientFun`, the smoothness witness is
`contMDiff_inducedOrientFun`. This is `∂M`'s reference orientation form (`refForm` of
the induced `OrientedManifold` instance assembled in P13). -/
noncomputable def inducedOrient :
    DiffForm (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (Bdry n M) n where
  toFun := inducedOrientFun
  contMDiff_toFun := contMDiff_inducedOrientFun

/-- The chart-coordinate read of the reference orientation form at `extChartAt x x` is nonzero.
This follows by collapsing the self coordinate-change via `formCoordChange_self` and applying
`OrientedManifold.refForm_ne`. -/
theorem formInCoord_refForm_self_ne_zero {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] (x : M) :
    formInCoord (𝓡∂ (n + 1))
      (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) x
      (extChartAt (𝓡∂ (n + 1)) x x) ≠ 0 := by
  rw [form_in_coord_eq_coord_change (𝓡∂ (n + 1))
      (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) x
      (mem_chart_source (EuclideanHalfSpace (n + 1)) x)]
  rw [formCoordChange_self (𝓡∂ (n + 1)) (n + 1)
      (achart (EuclideanHalfSpace (n + 1)) x) x
      (mem_chart_source (EuclideanHalfSpace (n + 1)) x)]
  exact OrientedManifold.refForm_ne x

/-- The `symmL` of the fiber bundle trivialization at `p` is injective, so a nonzero model
vector `v` maps to a nonzero fiber element. -/
theorem trivializationAt_symmL_ne_zero {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M) (v : EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) (hv : v ≠ 0) :
    Trivialization.symmL ℝ
      (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
        (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p) p
      v ≠ 0 := by
  intro h
  have hp := mem_baseSet_trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p
  let e := trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p
  apply hv
  have hcle_h : (e.continuousLinearEquivAt ℝ p hp).symm v = 0 := by
    have := e.symm_continuousLinearEquivAt_eq (R := ℝ) hp
    exact congrFun this v ▸ h
  exact (e.continuousLinearEquivAt ℝ p hp).symm.injective
    (hcle_h.trans (map_zero _).symm)

/-- The `p`-trivialization readout of `inducedOrientChartFun q p` equals the `q`-formula
precomposed by the `formBundleCore` coordinate-change cocycle from the `p`-chart to the
`q`-chart. -/
theorem trivializationAt_inducedOrientChartFun_eq {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M]
    (q p : Bdry n M) (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source) :
    ((trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
        (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p)
        ⟨p, inducedOrientChartFun q p⟩).2
      = ContinuousAlternatingMap.compContinuousLinearMapCLM
          ((tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).coordChange
            (achart (EuclideanSpace ℝ (Fin n)) p) (achart (EuclideanSpace ℝ (Fin n)) q) p)
          (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
            ((formInCoord (𝓡∂ (n + 1))
                (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M))
                q.val (extChartAt (𝓡∂ (n + 1)) q.val p.val)).curryLeft
              (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0))) := by
  have hb : p ∈ (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber q).baseSet := hp
  have h_read : ((trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p)
      ⟨p, inducedOrientChartFun q p⟩).2 = inducedOrientChartFun q p :=
    congrArg Prod.snd
      ((formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).localTrivAt_apply_mk
        p (inducedOrientChartFun q p))
  rw [h_read]
  simp only [inducedOrientChartFun]
  rw [(formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).trivializationAt_symmL
    (R := ℝ) hb]
  rfl

/-- Proportionality of trivialization readouts at `p` lifts to proportionality in the fiber:
if the readouts of `v` and `w` satisfy `readout v = c • readout w`, then `v = c • w`. -/
theorem smul_of_trivializationAt_smul {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M)
    (v w : (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p)
    (c : ℝ)
    (h : ((trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
          (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p)
          ⟨p, v⟩).2
        = c • ((trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
          (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p)
          ⟨p, w⟩).2) :
    v = c • w := by
  have hp : p ∈ (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p).baseSet :=
    FiberBundle.mem_baseSet_trivializationAt _ _ _
  apply (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p)
      |>.continuousLinearEquivAt ℝ p hp |>.injective
  rw [(trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p)
      |>.continuousLinearEquivAt ℝ p hp |>.map_smul]
  exact h

/-- The anchored induced boundary orientation chart function `inducedOrientChartFun p p` is
nonzero at every `p : Bdry n M`. The proof chains `formInCoord_refForm_self_ne_zero`,
`curry_face_ne_zero`, and `trivializationAt_symmL_ne_zero`. -/
theorem inducedOrientChartFun_self_ne_zero {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M]
    (p : Bdry n M) : inducedOrientChartFun p p ≠ 0 := by
  have h1 : formInCoord (𝓡∂ (n + 1))
      (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) p.val
      (extChartAt (𝓡∂ (n + 1)) p.val p.val) ≠ 0 :=
    formInCoord_refForm_self_ne_zero p.val
  have h2 : ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
      ((formInCoord (𝓡∂ (n + 1))
          (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) p.val
          (extChartAt (𝓡∂ (n + 1)) p.val p.val)).curryLeft
        (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)) ≠ 0 :=
    curry_face_ne_zero _ h1
  have h3 : Trivialization.symmL ℝ
      (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
        (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p) p
      (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
        ((formInCoord (𝓡∂ (n + 1))
            (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) p.val
            (extChartAt (𝓡∂ (n + 1)) p.val p.val)).curryLeft
          (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0))) ≠ 0 :=
    trivializationAt_symmL_ne_zero p _ h2
  exact h3

/-- For `p` in the source of `chartAt q`, the candidate `inducedOrientChartFun q p` is a
positive real multiple of the anchor `inducedOrientChartFun p p`. The positive factor comes
from the normal derivative of the half-space boundary transition. -/
theorem inducedOrientChartFun_eq_pos_smul_self {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M]
    (q p : Bdry n M) (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source) :
    ∃ c : ℝ, 0 < c ∧ inducedOrientChartFun q p = c • inducedOrientChartFun p p := by
  have h_read := trivializationAt_inducedOrientChartFun_eq q p hp
  have h_model := model_ray_pos q p hp
  obtain ⟨c, hc, hmodel⟩ := h_model
  refine ⟨c, hc, smul_of_trivializationAt_smul p _ _ c ?_⟩
  rw [h_read, chartfun_triv_read p p (mem_chart_source _ _), hmodel]

/-- A weighted sum `∑ i, w i • g i` is nonzero when: the weights `w` are nonneg and sum to 1,
a fixed vector `v ≠ 0` is given, and every nonzero-weight `g i` is a positive multiple of `v`. -/
theorem sum_smul_ne_zero_of_pos_smul {ι : Type*} {V : Type*} [AddCommGroup V] [Module ℝ V]
    (s : Finset ι) (w : ι → ℝ) (g : ι → V) (v : V)
    (hv : v ≠ 0) (hw0 : ∀ i, 0 ≤ w i) (hsum : ∑ i ∈ s, w i = 1)
    (hray : ∀ i, w i ≠ 0 → ∃ c : ℝ, 0 < c ∧ g i = c • v) :
    ∑ i ∈ s, w i • g i ≠ 0 := by
  classical
  set c : ι → ℝ := fun i => if h : w i ≠ 0 then (hray i h).choose else 0 with hc
  have hkey : ∑ i ∈ s, w i • g i = (∑ i ∈ s, w i * c i) • v := by
    rw [Finset.sum_smul]
    refine Finset.sum_congr rfl fun i _ => ?_
    by_cases h : w i ≠ 0
    · rw [hc]
      simp only [dif_pos h]
      rw [mul_smul]
      exact congrArg (w i • ·) (hray i h).choose_spec.2
    · push_neg at h
      simp [h]
  rw [hkey]
  refine smul_ne_zero (ne_of_gt ?_) hv
  have hex : ∃ i ∈ s, w i ≠ 0 := by
    by_contra hcon
    push_neg at hcon
    have : ∑ i ∈ s, w i = 0 := Finset.sum_eq_zero hcon
    rw [this] at hsum
    exact zero_ne_one hsum
  obtain ⟨i₀, hi₀s, hi₀⟩ := hex
  refine Finset.sum_pos' (fun i _ => ?_) ⟨i₀, hi₀s, ?_⟩
  · by_cases h : w i ≠ 0
    · have hcpos : 0 < c i := by
        rw [hc]; simp only [dif_pos h]; exact (hray i h).choose_spec.1
      exact mul_nonneg (hw0 i) hcpos.le
    · push_neg at h
      simp [h]
  · have hcpos : 0 < c i₀ := by
      rw [hc]; simp only [dif_pos hi₀]; exact (hray i₀ hi₀).choose_spec.1
    exact mul_pos (lt_of_le_of_ne (hw0 i₀) (Ne.symm hi₀)) hcpos

/-- A nonzero partition-of-unity weight `inducedOrientPOU n M q p ≠ 0` implies that `p` lies
in the source of `chartAt q`, by POU subordination to the atlas. -/
theorem mem_chartAt_source_of_inducedOrientPOU_ne_zero {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M]
    [T2Space (Bdry n M)] [SigmaCompactSpace (Bdry n M)]
    (q p : Bdry n M) (hq : inducedOrientPOU n M q p ≠ 0) :
    p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source := by
  have hspec := (SmoothPartitionOfUnity.exists_isSubordinate_chartAt_source
    (M := Bdry n M) (I := 𝓘(ℝ, EuclideanSpace ℝ (Fin n)))).choose_spec
  simp only [inducedOrientPOU] at hq
  exact hspec q (subset_tsupport _ (Function.mem_support.mpr hq))

/-- The POU-glued form `inducedOrientFun p` is nonzero, given that the anchor
`inducedOrientChartFun p p ≠ 0` and that every nonzero-weight chart candidate is a positive
multiple of that anchor. -/
theorem inducedOrientFun_ne_zero {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M]
    [T2Space (Bdry n M)] [SigmaCompactSpace (Bdry n M)]
    (p : Bdry n M)
    (hray : ∀ q : Bdry n M, inducedOrientPOU n M q p ≠ 0 →
      ∃ c : ℝ, 0 < c ∧ inducedOrientChartFun q p = c • inducedOrientChartFun p p)
    (hanchor : inducedOrientChartFun p p ≠ 0) :
    inducedOrientFun p ≠ 0 := by
  have heq : inducedOrientFun p = ∑ q ∈ (inducedOrientPOU n M).finsupport p,
      inducedOrientPOU n M q p • inducedOrientChartFun q p :=
    ((inducedOrientPOU n M).sum_finsupport_smul_eq_finsum p
      (fun q _ => inducedOrientChartFun q p)).symm
  have key : ∑ q ∈ (inducedOrientPOU n M).finsupport p,
      inducedOrientPOU n M q p • inducedOrientChartFun q p ≠ 0 :=
    sum_smul_ne_zero_of_pos_smul ((inducedOrientPOU n M).finsupport p)
      (fun q => inducedOrientPOU n M q p)
      (fun q => inducedOrientChartFun q p)
      (inducedOrientChartFun p p)
      hanchor (fun q => (inducedOrientPOU n M).nonneg q p)
      ((inducedOrientPOU n M).sum_finsupport p (Set.mem_univ p)) hray
  rw [heq]
  exact key

/-- **Nonvanishing of the induced boundary orientation form**: `inducedOrient p ≠ 0` for every
`p : Bdry n M`. The proof assembles chart-local nonvanishing
(`inducedOrientChartFun_self_ne_zero`), positive-ray compatibility across charts
(`inducedOrientChartFun_eq_pos_smul_self`), and POU-gluing (`inducedOrientFun_ne_zero`). -/
theorem inducedOrient_ne_zero : ∀ {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M]
    [T2Space (Bdry n M)] [SigmaCompactSpace (Bdry n M)],
    ∀ p : Bdry n M, inducedOrient p ≠ 0 := by
  intro n M _ _ _ _ _ _ p
  have h_anchor : inducedOrientChartFun p p ≠ 0 := inducedOrientChartFun_self_ne_zero p
  have h_mem : ∀ q : Bdry n M, inducedOrientPOU n M q p ≠ 0 →
      p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source :=
    fun q hq => mem_chartAt_source_of_inducedOrientPOU_ne_zero q p hq
  have h_ray : ∀ q : Bdry n M, p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source →
      ∃ c : ℝ, 0 < c ∧ inducedOrientChartFun q p = c • inducedOrientChartFun p p :=
    fun q hq => inducedOrientChartFun_eq_pos_smul_self q p hq
  exact inducedOrientFun_ne_zero p (fun q hq => h_ray q (h_mem q hq)) h_anchor

end Library.Geometry.Manifold.InducedOrientNonzero
