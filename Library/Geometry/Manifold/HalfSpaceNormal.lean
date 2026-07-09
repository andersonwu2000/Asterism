import Library.Geometry.Manifold.DiffFormBundle        -- DiffForm
import Library.Geometry.Manifold.FaceEmbedAlts
import Library.Geometry.Manifold.InducedOrientDefs       -- inducedOrientFun (P12)
import Library.Geometry.Manifold.InducedOrientSmooth      -- contMDiff_inducedOrientFun (P12)
import Library.Geometry.Manifold.StokesIntegralDefs      -- OrientedManifold (+ refForm)
import Library.Geometry.ManifoldBdry.BdryIsManifold       -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBdry.FaceEmbedLemmas
import Library.Geometry.ManifoldBoundary.CompactBdry      -- Bdry
import Mathlib.Analysis.Calculus.FDeriv.Comp
import Mathlib.Analysis.Calculus.LocalExtr.Basic
import Mathlib.Analysis.Calculus.TangentCone.Defs
import Mathlib.Analysis.Convex.Segment
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.Normed.Lp.PiLp
import Mathlib.Analysis.Normed.Module.Alternating.Basic
import Mathlib.Analysis.Normed.Module.Alternating.Curry
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.VectorBundle.Tangent
import Mathlib.Topology.VectorBundle.Basic

/-!
# Half-space normal component positivity

This file establishes that the outward-pointing normal to the boundary of a half-space
manifold has a strictly positive component in the e₀ direction after applying any ambient
tangent coordinate change. The key steps are: (1) e₀ does not lie in the range of
`faceEmbedL`; (2) the coordinate change sends e₀ to `a • e₀ + faceEmbedL t` with `a > 0`
(the zero-component of the transition function is a local minimum on the half-space, forcing
the directional derivative along e₀ to be nonneg, and injectivity of the cocycle forces it
to be positive); (3) this positivity propagates to the oriented boundary integral.

## Main statements

- `e0_not_mem_face_range`: e₀ is not in the range of `faceEmbedL`.
- `ambient_normal_deriv_pos`: the ambient coordinate change sends e₀ to `a • e₀ + faceEmbedL t`
  with `a > 0`.
- `model_ray_pos`: the boundary orientation form is scaled by a positive constant under a
  coordinate change.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.FaceEmbedAlts
open Library.Geometry.Manifold.InducedOrientDefs
open Library.Geometry.Manifold.InducedOrientSmooth
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.FaceEmbedLemmas
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open scoped Manifold
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.HalfSpaceNormal

/-- e₀ is not in the range of `faceEmbedL`, because `faceEmbedL` maps into coordinates 1..n
(the zeroth component of any `faceEmbedL v` is 0, while e₀ has zeroth component 1). -/
theorem e0_not_mem_face_range (n : ℕ) :
    EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 ∉
      Set.range ⇑(faceEmbedL (n := n)) := by
  intro ⟨v, hv⟩
  have key : ((EuclideanSpace.proj (0 : Fin (n + 1))).comp (faceEmbedL (n := n))) = 0 := by
    ext x
    change (EuclideanSpace.proj (0 : Fin (n + 1))) (faceEmbedL x) = 0
    simp only [faceEmbedL, ContinuousLinearMap.sum_apply, ContinuousLinearMap.smulRight_apply]
    rw [map_sum (EuclideanSpace.proj (0 : Fin (n + 1)))]
    simp only [map_smul]
    apply Finset.sum_eq_zero
    intro i _
    simp only [EuclideanSpace.proj, PiLp.proj, ContinuousLinearMap.coe_mk', PiLp.projₗ_apply,
      EuclideanSpace.basisFun_apply, EuclideanSpace.single, PiLp.ofLp_single, Pi.single_apply,
      (Fin.succ_ne_zero i).symm, ↓reduceIte, smul_zero]
  have h1 : (EuclideanSpace.proj (0 : Fin (n + 1))) (faceEmbedL (n := n) v) = 0 := by
    have := DFunLike.congr_fun key v
    simp only [ContinuousLinearMap.comp_apply, ContinuousLinearMap.zero_apply] at this
    exact this
  have h0 : (EuclideanSpace.proj (0 : Fin (n + 1)))
      (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0) = 1 := by
    simp [EuclideanSpace.proj, PiLp.proj, EuclideanSpace.basisFun_apply, EuclideanSpace.single]
  rw [← hv, h1] at h0
  norm_num at h0

/-- e₀ lies in the positive tangent cone of the half-space range `𝓡∂(n+1)` at any
boundary-adjacent point `a`, because the segment `[a, a + e₀]` stays in `{y | 0 ≤ y 0}`. -/
theorem e0_mem_posTangentConeAt {n : ℕ} (a : EuclideanSpace ℝ (Fin (n + 1)))
    (ha : 0 ≤ a 0) :
    EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 ∈
      posTangentConeAt (Set.range (𝓡∂ (n + 1))) a := by
  apply mem_posTangentConeAt_of_segment_subset
  rw [range_modelWithCornersEuclideanHalfSpace]
  intro x hx
  simp only [Set.mem_setOf_eq]
  rw [segment_eq_image'] at hx
  obtain ⟨t, ht, rfl⟩ := hx
  simp only [add_sub_cancel_left]
  simp only [WithLp.ofLp_add, WithLp.ofLp_smul, Pi.add_apply, Pi.smul_apply, smul_eq_mul,
    EuclideanSpace.basisFun_apply, PiLp.single_apply, if_true]
  linarith [ht.1]

/-- The zeroth coordinate of `extChartAt (𝓡∂ (n+1)) x w` is nonneg, because `chartAt` lands
in the half-space subtype `{y | 0 ≤ y 0}`. -/
theorem extchart_zeroth_nonneg {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] (x w : M) :
    0 ≤ extChartAt (𝓡∂ (n + 1)) x w 0 := by
  exact (chartAt (EuclideanHalfSpace (n + 1)) x w).property

/-- Any vector `v : EuclideanSpace ℝ (Fin (n + 1))` decomposes as
`v = v 0 • e₀ + faceEmbedL t` for some `t : EuclideanSpace ℝ (Fin n)`.
The witness is the tail `t i = v i.succ`. -/
theorem vec_decomp_normal_face {n : ℕ} (v : EuclideanSpace ℝ (Fin (n + 1))) :
    ∃ t : EuclideanSpace ℝ (Fin n),
      v = v 0 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t := by
  refine ⟨WithLp.toLp 2 (fun (i : Fin n) => v.ofLp i.succ), ?_⟩
  ext j
  refine j.cases ?_ (fun i => ?_)
  · simp [faceEmbedL, EuclideanSpace.basisFun_apply, EuclideanSpace.single,
      ContinuousLinearMap.sum_apply, ContinuousLinearMap.smulRight_apply,
      EuclideanSpace.proj, PiLp.proj]
  · simp [faceEmbedL, EuclideanSpace.basisFun_apply, EuclideanSpace.single,
      ContinuousLinearMap.sum_apply, ContinuousLinearMap.smulRight_apply,
      EuclideanSpace.proj, PiLp.proj, PiLp.projₗ_apply]
    simp only [Pi.single_apply, Fin.succ_inj, mul_ite, mul_one, mul_zero,
      Finset.sum_ite_eq, Finset.mem_univ, if_true]

/-- The ambient tangent coordinate change `coordChange(q → p) ∘ coordChange(p → q)` equals the
identity at `p.val`, via the cocycle law followed by the self-change identity. -/
theorem ambient_coordchange_inv {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (q p : Bdry n M) (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source)
    (v : EuclideanSpace ℝ (Fin (n + 1))) :
    (tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
      (achart (EuclideanHalfSpace (n + 1)) p.val)
      (achart (EuclideanHalfSpace (n + 1)) q.val) p.val
      ((tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
        (achart (EuclideanHalfSpace (n + 1)) q.val)
        (achart (EuclideanHalfSpace (n + 1)) p.val) p.val v) = v := by
  have h_src : p.val ∈ (extChartAt (𝓡∂ (n + 1)) q.val).source := by
    rw [extChartAt_source]
    exact Set.mem_of_mem_inter_left hp
  rw [tangentCoordChange_comp (I := 𝓡∂ (n + 1)) (M := M)
    ⟨⟨h_src, mem_extChartAt_source _⟩, h_src⟩]
  exact tangentCoordChange_self h_src

/-- The zeroth component of `(coordChange q → p at p) e₀` is nonneg. The proof uses the
one-sided Fréchet derivative of the transition function's zeroth coordinate: that function is
nonneg on the half-space and equals zero at the anchor, so the directional derivative along e₀
(in the positive tangent cone) is nonneg. -/
theorem ambient_normal_component_nonneg {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (q p : Bdry n M) (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source) :
    0 ≤ (tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
        (achart (EuclideanHalfSpace (n + 1)) q.val)
        (achart (EuclideanHalfSpace (n + 1)) p.val) p.val
        (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0) 0 := by
  have h_src : p.val ∈ (extChartAt (𝓡∂ (n + 1)) q.val).source := by
    rw [extChartAt_source]
    exact Set.mem_of_mem_inter_left hp
  have h_within : HasFDerivWithinAt
      (extChartAt (𝓡∂ (n + 1)) p.val ∘ (extChartAt (𝓡∂ (n + 1)) q.val).symm)
      ((tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
        (achart (EuclideanHalfSpace (n + 1)) q.val)
        (achart (EuclideanHalfSpace (n + 1)) p.val) p.val)
      (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) q.val p.val) :=
    hasFDerivWithinAt_tangentCoordChange ⟨h_src, mem_extChartAt_source _⟩
  have h_scalar : HasFDerivWithinAt
      (⇑(EuclideanSpace.proj (0 : Fin (n + 1))) ∘
        (extChartAt (𝓡∂ (n + 1)) p.val ∘ (extChartAt (𝓡∂ (n + 1)) q.val).symm))
      ((EuclideanSpace.proj (0 : Fin (n + 1))).comp
        ((tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
          (achart (EuclideanHalfSpace (n + 1)) q.val)
          (achart (EuclideanHalfSpace (n + 1)) p.val) p.val))
      (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) q.val p.val) :=
    (EuclideanSpace.proj (0 : Fin (n + 1))).hasFDerivAt.comp_hasFDerivWithinAt _ h_within
  have h_nonneg : ∀ (x : M) (w : M), 0 ≤ extChartAt (𝓡∂ (n + 1)) x w 0 :=
    extchart_zeroth_nonneg
  have h_anchor : extChartAt (𝓡∂ (n + 1)) p.val p.val 0 = 0 :=
    Library.Geometry.ManifoldBoundary.BoundaryCoord.boundary_extChartAt_coord_zero p p
      (mem_extChartAt_source _)
  have h_min : IsLocalMinOn
      (⇑(EuclideanSpace.proj (0 : Fin (n + 1))) ∘
        (extChartAt (𝓡∂ (n + 1)) p.val ∘ (extChartAt (𝓡∂ (n + 1)) q.val).symm))
      (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) q.val p.val) := by
    refine Filter.Eventually.of_forall fun y => ?_
    simp only [Function.comp_apply, PiLp.proj_apply,
      (extChartAt (𝓡∂ (n + 1)) q.val).left_inv h_src, h_anchor]
    exact h_nonneg p.val _
  have h_cone : EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 ∈
      posTangentConeAt (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) q.val p.val) :=
    e0_mem_posTangentConeAt _ (h_nonneg q.val p.val)
  have h := h_min.hasFDerivWithinAt_nonneg h_scalar h_cone
  simpa using h

/-- The boundary tangent coordinate change `coordChange(q → p)` inverts `coordChange(p → q)`
at `p`, via the `VectorBundleCore` cocycle law followed by the self-change identity. -/
theorem bdry_coordchange_inv {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (q p : Bdry n M) (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source)
    (w : EuclideanSpace ℝ (Fin n)) :
    (tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).coordChange
      (achart (EuclideanSpace ℝ (Fin n)) q) (achart (EuclideanSpace ℝ (Fin n)) p) p
      ((tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).coordChange
        (achart (EuclideanSpace ℝ (Fin n)) p) (achart (EuclideanSpace ℝ (Fin n)) q) p w)
    = w := by
  have hmem : p ∈ (tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).baseSet
        (achart (EuclideanSpace ℝ (Fin n)) p) ∩
      (tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).baseSet
        (achart (EuclideanSpace ℝ (Fin n)) q) ∩
      (tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).baseSet
        (achart (EuclideanSpace ℝ (Fin n)) p) := by
    simp only [tangentBundleCore_baseSet, coe_achart]
    exact ⟨⟨mem_chart_source _ _, hp⟩, mem_chart_source _ _⟩
  rw [(tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).coordChange_comp
      (achart (EuclideanSpace ℝ (Fin n)) p) (achart (EuclideanSpace ℝ (Fin n)) q)
      (achart (EuclideanSpace ℝ (Fin n)) p) p hmem]
  exact (tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).coordChange_self
    (achart (EuclideanSpace ℝ (Fin n)) p) p (mem_achart_source _ _) _

/-- The q-anchored `formInCoord` equals the p-anchored one precomposed with the ambient tangent
coordinate change `coordChange(q → p)` at `p`. Follows from `form_coord_change_transport_self`
and unfolding `formCoordChange`. -/
theorem formincoord_q_eq_comp_p {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M]
    (q p : Bdry n M) (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source) :
    formInCoord (𝓡∂ (n + 1))
        (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M))
        q.val (extChartAt (𝓡∂ (n + 1)) q.val p.val)
      = ContinuousAlternatingMap.compContinuousLinearMapCLM
          ((tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
            (achart (EuclideanHalfSpace (n + 1)) q.val)
            (achart (EuclideanHalfSpace (n + 1)) p.val) p.val)
          (formInCoord (𝓡∂ (n + 1))
            (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M))
            p.val (extChartAt (𝓡∂ (n + 1)) p.val p.val)) := by
  have h_val : p.val ∈ (chartAt (EuclideanHalfSpace (n + 1)) q.val).source :=
    Set.mem_of_mem_inter_left hp
  have h_transport :=
    form_coord_change_transport_self
      (𝓡∂ (n + 1)) (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) q.val p.val h_val
  simp only [Library.Geometry.Manifold.FormCoordChange.formCoordChange] at h_transport
  exact h_transport.symm

/-- The ambient tangent coordinate change intertwines `faceEmbedL` with the boundary tangent
coordinate change: `coordChange_ambient(q → p) ∘ faceEmbedL = faceEmbedL ∘ coordChange_bdry(q → p)`.
Proved via uniqueness of the Fréchet derivative using `extChartAt_trans_comp_faceEmbed_hasFDerivAt`,
`faceEmbed_comp_bdry_trans_hasFDerivAt`, and `extChartAt_trans_faceEmbed_eventuallyEq`. -/
theorem ambient_face_intertwine {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (q p : Bdry n M) (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source) :
    (((tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
        (achart (EuclideanHalfSpace (n + 1)) q.val)
        (achart (EuclideanHalfSpace (n + 1)) p.val) p.val).comp faceEmbedL)
      = faceEmbedL.comp ((tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).coordChange
          (achart (EuclideanSpace ℝ (Fin n)) q) (achart (EuclideanSpace ℝ (Fin n)) p) p) := by
  have h1 := extChartAt_trans_comp_faceEmbed_hasFDerivAt q p hp
  have heq := extChartAt_trans_faceEmbed_eventuallyEq q p hp
  have h2 := faceEmbed_comp_bdry_trans_hasFDerivAt q p hp
  exact (h1.congr_of_eventuallyEq heq.symm).unique h2

/-- The ambient coordinate change `coordChange(q → p)` does not send e₀ into the range of
`faceEmbedL`. The proof uses the cocycle inverse `ambient_coordchange_inv`, the intertwining
lemma `ambient_face_intertwine`, and the boundary cocycle inverse `bdry_coordchange_inv` to
show that if `coordChange(q → p) e₀ = faceEmbedL t`, then `faceEmbedL s = e₀` for some `s`,
contradicting `e0_not_mem_face_range`. -/
theorem ambient_e0_not_face_range {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (q p : Bdry n M) (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source) :
    (tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
        (achart (EuclideanHalfSpace (n + 1)) q.val)
        (achart (EuclideanHalfSpace (n + 1)) p.val) p.val
        (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0) ∉ Set.range ⇑(faceEmbedL (n := n)) := by
  rintro ⟨t, ht⟩
  have h_e0 : EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 ∉
      Set.range ⇑(faceEmbedL (n := n)) := e0_not_mem_face_range n
  have h_inv : ∀ v : EuclideanSpace ℝ (Fin (n + 1)),
      (tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
        (achart (EuclideanHalfSpace (n + 1)) p.val)
        (achart (EuclideanHalfSpace (n + 1)) q.val) p.val
        ((tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
          (achart (EuclideanHalfSpace (n + 1)) q.val)
          (achart (EuclideanHalfSpace (n + 1)) p.val) p.val v) = v :=
    fun v => ambient_coordchange_inv q p hp v
  set s : EuclideanSpace ℝ (Fin n) :=
    (tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).coordChange
      (achart (EuclideanSpace ℝ (Fin n)) p) (achart (EuclideanSpace ℝ (Fin n)) q) p t
    with hs_def
  have hs : (tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).coordChange
      (achart (EuclideanSpace ℝ (Fin n)) q) (achart (EuclideanSpace ℝ (Fin n)) p) p s = t :=
    bdry_coordchange_inv q p hp t
  have hint := congrArg
    (fun L : EuclideanSpace ℝ (Fin n) →L[ℝ] EuclideanSpace ℝ (Fin (n + 1)) => L s)
    (ambient_face_intertwine q p hp)
  simp only [ContinuousLinearMap.comp_apply] at hint
  rw [hs, ht] at hint
  have h1 := h_inv (faceEmbedL s)
  have h2 := h_inv (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)
  rw [hint] at h1
  exact h_e0 ⟨s, h1.symm.trans h2⟩

/-- The ambient coordinate change `coordChange(q → p)` sends e₀ to `a • e₀ + faceEmbedL t`
for some `a > 0` and `t : EuclideanSpace ℝ (Fin n)`. The positivity of `a` combines
`ambient_normal_component_nonneg` (giving `a ≥ 0`) with `ambient_e0_not_face_range`
(ruling out `a = 0`, which would place the image in `range faceEmbedL`). -/
theorem ambient_normal_deriv_pos {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (q p : Bdry n M) (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source) :
    ∃ a : ℝ, 0 < a ∧ ∃ t : EuclideanSpace ℝ (Fin n),
      (tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
        (achart (EuclideanHalfSpace (n + 1)) q.val)
        (achart (EuclideanHalfSpace (n + 1)) p.val) p.val
        (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)
      = a • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t := by
  have h_nonneg := ambient_normal_component_nonneg q p hp
  have h_notface := ambient_e0_not_face_range q p hp
  obtain ⟨t, ht⟩ := vec_decomp_normal_face ((tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
      (achart (EuclideanHalfSpace (n + 1)) q.val)
      (achart (EuclideanHalfSpace (n + 1)) p.val) p.val
      (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0))
  refine ⟨_, ?_, t, ht⟩
  rcases h_nonneg.lt_or_eq with h | h
  · exact h
  · refine absurd ?_ h_notface
    rw [ht, ← h, zero_smul, zero_add]
    exact ⟨t, rfl⟩

/-- Under a chart change `q → p`, the boundary orientation form is scaled by a positive
constant `c > 0`. Specifically, the `q`-anchored form composed with the boundary coordinate
change equals `c` times the `p`-anchored form. The proof combines `formincoord_q_eq_comp_p`,
`ambient_face_intertwine`, `bdry_coordchange_inv`, and `ambient_normal_deriv_pos`, then closes
by `alt_normal_eval_smul` with `c := a`. -/
theorem model_ray_pos {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M]
    (q p : Bdry n M) (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source) :
    ∃ c : ℝ, 0 < c ∧
      ContinuousAlternatingMap.compContinuousLinearMapCLM
          ((tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).coordChange
            (achart (EuclideanSpace ℝ (Fin n)) p) (achart (EuclideanSpace ℝ (Fin n)) q) p)
          (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
            ((formInCoord (𝓡∂ (n + 1))
                (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M))
                q.val (extChartAt (𝓡∂ (n + 1)) q.val p.val)).curryLeft
              (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)))
        = c • ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
            ((formInCoord (𝓡∂ (n + 1))
                (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M))
                p.val (extChartAt (𝓡∂ (n + 1)) p.val p.val)).curryLeft
              (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)) := by
  have h_pull := formincoord_q_eq_comp_p q p hp
  have h_int := ambient_face_intertwine q p hp
  have h_inv := bdry_coordchange_inv q p hp
  obtain ⟨a, ha, t, hAe⟩ := ambient_normal_deriv_pos q p hp
  refine ⟨a, ha, ?_⟩
  rw [h_pull]
  refine ContinuousAlternatingMap.ext fun w => ?_
  simp only [ContinuousAlternatingMap.compContinuousLinearMapCLM_apply,
    ContinuousAlternatingMap.compContinuousLinearMap_apply,
    ContinuousAlternatingMap.curryLeft_apply_apply,
    ContinuousAlternatingMap.smul_apply]
  exact alt_normal_eval_smul _ _ _ _ a t h_int h_inv hAe w

end Library.Geometry.Manifold.HalfSpaceNormal
