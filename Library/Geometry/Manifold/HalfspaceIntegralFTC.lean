import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.InducedOrientNonzero         -- inducedOrient, inducedOrient_ne_zero
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBdry.PullbackBdryDefs         -- pullbackBdryFun
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff    -- contMDiff_pullbackBdryFun
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.Normed.Lp.MeasurableSpace
import Mathlib.MeasureTheory.Constructions.BorelSpace.Basic
import Mathlib.MeasureTheory.Constructions.BorelSpace.Order
import Mathlib.MeasureTheory.Constructions.Pi
import Mathlib.MeasureTheory.Function.LocallyIntegrable
import Mathlib.MeasureTheory.Integral.Bochner.Set
import Mathlib.MeasureTheory.Integral.IntegrableOn
import Mathlib.MeasureTheory.Integral.Prod
import Mathlib.MeasureTheory.MeasurableSpace.Embedding
import Mathlib.MeasureTheory.MeasurableSpace.Prod
import Mathlib.MeasureTheory.Measure.Lebesgue.Basic
import Mathlib.MeasureTheory.Measure.Prod
import Mathlib.Topology.Algebra.Group.Basic
import Mathlib.Topology.Algebra.Module.FiniteDimension
import Mathlib.Topology.Algebra.Support

/-!
# Half-space integral change of variables

This file establishes the reparametrization `Φ : EuclideanSpace ℝ (Fin n) × ℝ →
EuclideanSpace ℝ (Fin (n+1))` defined by `Φ (t, s) = s • e₀ + faceEmbedL t`, where `e₀`
is the zeroth standard basis vector. This map is a closed embedding, a measurable embedding,
and a measure-preserving map from the product measure to the ambient Euclidean volume.

The main application is a change-of-variables formula expressing an integral over the
closed half-space `{y | 0 ≤ y 0}` as an iterated integral over `EuclideanSpace ℝ (Fin n) × Ioi 0`.

## Main statements

- `measurableSet_halfspace_zero_coord`: the half-space `{y | 0 ≤ y 0}` is measurable.
- `reparam_closed_embedding`: `Φ` is a closed embedding.
- `reparam_measure_preserving`: `Φ` is volume-preserving.
- `continuousOn_integrableOn_of_isClosed_hasCompactSupport`: a continuous compactly supported
  function on a closed set is integrable there.
- `halfspace_within_integral_change_var`: the change-of-variables identity for integrals
  over the half-space.
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

namespace Library.Geometry.Manifold.HalfspaceIntegralFTC

variable {n : ℕ}

/-- The closed half-space `{y : EuclideanSpace ℝ (Fin (n+1)) | 0 ≤ y 0}` is measurable,
since the zeroth coordinate projection is measurable via `WithLp.measurable_ofLp`. -/
theorem measurableSet_halfspace_zero_coord :
    MeasurableSet {y : EuclideanSpace ℝ (Fin (n+1)) | 0 ≤ y 0} :=
  measurableSet_le measurable_const
    ((measurable_pi_apply 0).comp (WithLp.measurable_ofLp 2 _))

/-- The function `s ↦ g (s • e₀ + faceEmbedL t)` has compact support whenever `g` does,
since the affine map `s ↦ s • e₀ + faceEmbedL t` is a closed embedding. -/
theorem slice_compact_support
    (g : EuclideanSpace ℝ (Fin (n + 1)) → ℝ) (hsupp : HasCompactSupport g)
    (t : EuclideanSpace ℝ (Fin n)) :
    HasCompactSupport
      (fun s : ℝ => g (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)) := by
  have he : EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 ≠ 0 := by simp
  have h_emb : Topology.IsClosedEmbedding
      (fun s : ℝ => s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t) :=
    (Homeomorph.addRight (faceEmbedL t)).isClosedEmbedding.comp
      (isClosedEmbedding_smul_left he)
  exact hsupp.comp_isClosedEmbedding h_emb

/-- The preimage of `{y | 0 ≤ y 0}` under `Φ (t, s) = s • e₀ + faceEmbedL t` equals
`univ ×ˢ Ioi 0` almost everywhere with respect to the product measure, since `Ici 0`
and `Ioi 0` differ only on the null set `{0}`. -/
theorem halfspace_preimage_ae_prod :
    ((fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1)
      ⁻¹' {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0})
      =ᵐ[(MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
          MeasureTheory.volume]
      (Set.univ ×ˢ Set.Ioi (0 : ℝ)) := by
  have hpre : ((fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
      q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1) ⁻¹'
      {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0}) = Set.univ ×ˢ Set.Ici 0 := by
    ext ⟨t, s⟩
    simp only [Set.mem_preimage, Set.mem_setOf_eq, Set.mem_prod, Set.mem_univ, Set.mem_Ici,
      true_and, faceEmbedL, EuclideanSpace.basisFun_apply,
      ContinuousLinearMap.sum_apply, ContinuousLinearMap.smulRight_apply, EuclideanSpace.proj,
      WithLp.ofLp_add, WithLp.ofLp_smul, WithLp.ofLp_sum, PiLp.ofLp_single]
    simp [Fin.succ_ne_zero]
  rw [hpre]
  exact MeasureTheory.Measure.set_prod_ae_eq
    (Filter.EventuallyEq.refl _ _) MeasureTheory.Ioi_ae_eq_Ici.symm

/-- The map `Φ (t, s) = s • e₀ + faceEmbedL t` is injective: the zeroth coordinate recovers
`s`, and the successor coordinates recover `t`. -/
theorem reparam_injective :
    Function.Injective
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1) := by
  intro ⟨t₁, s₁⟩ ⟨t₂, s₂⟩ h
  have heq : ∀ i : Fin (n + 1),
      (WithLp.ofLp (s₁ • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t₁)) i =
      (WithLp.ofLp (s₂ • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t₂)) i :=
    fun i => congr_fun (congrArg WithLp.ofLp h) i
  simp only [faceEmbedL, EuclideanSpace.basisFun_apply,
    ContinuousLinearMap.sum_apply, ContinuousLinearMap.smulRight_apply, EuclideanSpace.proj,
    WithLp.ofLp_add, WithLp.ofLp_smul, WithLp.ofLp_sum, PiLp.ofLp_single] at heq
  refine Prod.ext ?_ ?_
  · apply PiLp.ext
    intro j
    have hj := heq j.succ
    simp only [Pi.add_apply, Pi.smul_apply, Finset.sum_apply,
               Pi.single_apply, Fin.succ_ne_zero, ↓reduceIte, smul_eq_mul, mul_zero,
               zero_add, Fin.succ_inj, mul_ite, mul_one,
               Finset.sum_ite_eq, Finset.mem_univ, PiLp.proj] at hj
    exact hj
  · have h0 := heq 0
    simp only [Pi.add_apply, Pi.smul_apply, Finset.sum_apply,
               Pi.single_apply, ↓reduceIte, smul_eq_mul, mul_one] at h0
    have hne : ∀ x : Fin n, ¬ (0 : Fin (n + 1)) = x.succ :=
      fun x => Ne.symm (Fin.succ_ne_zero x)
    simp only [hne, if_false, mul_zero, Finset.sum_const_zero, add_zero] at h0
    exact h0

/-- The affine reparametrization `Φ (t, s) = s • e₀ + faceEmbedL t` is a closed embedding.
It is realized as an injective continuous linear map between finite-dimensional spaces,
hence a closed embedding by `LinearMap.isClosedEmbedding_of_injective`. -/
theorem reparam_closed_embedding :
    Topology.IsClosedEmbedding
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1) := by
  have hinj := reparam_injective (n := n)
  set e0 : EuclideanSpace ℝ (Fin (n + 1)) := EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 with he0
  let L : (EuclideanSpace ℝ (Fin n) × ℝ) →L[ℝ] EuclideanSpace ℝ (Fin (n + 1)) :=
    (ContinuousLinearMap.snd ℝ (EuclideanSpace ℝ (Fin n)) ℝ).smulRight e0 +
      faceEmbedL.comp (ContinuousLinearMap.fst ℝ (EuclideanSpace ℝ (Fin n)) ℝ)
  have hL : (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1) = ⇑L := by
    funext q
    simp [L, he0]
  rw [hL]
  rw [hL] at hinj
  exact LinearMap.isClosedEmbedding_of_injective
    (f := L.toLinearMap) (LinearMap.ker_eq_bot.mpr hinj)

/-- There exists a measurable equivalence `e : EuclideanSpace ℝ (Fin n) × ℝ ≃ᵐ
EuclideanSpace ℝ (Fin (n+1))` whose underlying function is `Φ (t, s) = s • e₀ + faceEmbedL t`.
The equivalence is given by the chain: swap, identity × `ofLp`, `piFinSuccAbove 0` inverse,
then `toLp`. -/
theorem reparam_measurable_equiv :
    ∃ e : (EuclideanSpace ℝ (Fin n) × ℝ) ≃ᵐ EuclideanSpace ℝ (Fin (n + 1)),
      ⇑e = fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1 := by
  refine ⟨(MeasurableEquiv.prodComm.trans
      (MeasurableEquiv.prodCongr (MeasurableEquiv.refl ℝ)
        (MeasurableEquiv.toLp 2 (Fin n → ℝ)).symm)).trans
      ((MeasurableEquiv.piFinSuccAbove (fun _ : Fin (n + 1) => ℝ) 0).symm.trans
        (MeasurableEquiv.toLp 2 (Fin (n + 1) → ℝ))), ?_⟩
  funext q
  obtain ⟨t, s⟩ := q
  apply PiLp.ext
  intro j
  refine Fin.cases ?_ (fun i => ?_) j
  · change s = (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t) 0
    simp [faceEmbedL, EuclideanSpace.basisFun_apply,
      ContinuousLinearMap.smulRight_apply, Fin.succ_ne_zero]
  · change t.ofLp i = (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t) i.succ
    simp [faceEmbedL, EuclideanSpace.basisFun_apply, Pi.single_apply,
      ContinuousLinearMap.smulRight_apply, Fin.succ_ne_zero, Fin.succ_inj]

/-- The reparametrization `Φ (t, s) = s • e₀ + faceEmbedL t` is a measurable embedding,
as it is the underlying map of a measurable equivalence (`reparam_measurable_equiv`). -/
theorem reparam_measurable_embedding :
    MeasurableEmbedding
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1) := by
  obtain ⟨e, he⟩ := reparam_measurable_equiv (n := n)
  rw [← he]
  exact e.measurableEmbedding

/-- The reparametrization `Φ (t, s) = s • e₀ + faceEmbedL t` is measure-preserving from
the product measure on `EuclideanSpace ℝ (Fin n) × ℝ` to the Euclidean volume on
`EuclideanSpace ℝ (Fin (n+1))`. The proof chains four standard measure-preserving maps:
swap, identity × `ofLp`, `piFinSuccAbove 0` inverse, and `toLp`. -/
theorem reparam_measure_preserving :
    MeasureTheory.MeasurePreserving
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1)
      ((MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
        MeasureTheory.volume)
      (MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin (n + 1)))) := by
  have h1 : MeasureTheory.MeasurePreserving
      (Prod.swap : EuclideanSpace ℝ (Fin n) × ℝ → ℝ × EuclideanSpace ℝ (Fin n))
      (MeasureTheory.volume.prod MeasureTheory.volume)
      (MeasureTheory.volume.prod MeasureTheory.volume) :=
    MeasureTheory.Measure.measurePreserving_swap
  have h2 : MeasureTheory.MeasurePreserving
      (Prod.map (id : ℝ → ℝ) (WithLp.ofLp : EuclideanSpace ℝ (Fin n) → (Fin n → ℝ)))
      (MeasureTheory.volume.prod MeasureTheory.volume)
      (MeasureTheory.volume.prod MeasureTheory.volume) :=
    (MeasureTheory.MeasurePreserving.id MeasureTheory.volume).prod
      (PiLp.volume_preserving_ofLp (Fin n))
  have h3 : MeasureTheory.MeasurePreserving
      ((MeasurableEquiv.piFinSuccAbove (fun _ : Fin (n + 1) => ℝ) 0).symm)
      (MeasureTheory.volume.prod MeasureTheory.volume)
      MeasureTheory.volume :=
    (MeasureTheory.volume_preserving_piFinSuccAbove (fun _ : Fin (n + 1) => ℝ) 0).symm
  have h4 : MeasureTheory.MeasurePreserving
      (WithLp.toLp 2 : (Fin (n + 1) → ℝ) → EuclideanSpace ℝ (Fin (n + 1)))
      MeasureTheory.volume MeasureTheory.volume :=
    PiLp.volume_preserving_toLp (Fin (n + 1))
  have hcomp := ((h4.comp h3).comp h2).comp h1
  convert hcomp using 1
  funext q
  ext i
  simp only [Function.comp_apply, MeasurableEquiv.piFinSuccAbove_symm_apply, WithLp.ofLp_toLp,
    Fin.insertNthEquiv_apply, Fin.insertNth_zero', Prod.map_fst, Prod.map_snd, id_eq,
    Prod.fst_swap, Prod.snd_swap]
  refine Fin.cases ?_ ?_ i
  · simp [faceEmbedL]
  · intro j
    simp [faceEmbedL, Pi.single_apply, Fin.succ_inj]

/-- A function that is continuous on a closed set and has compact support is integrable on
that closed set with respect to any locally finite measure on a Borel space. -/
theorem continuousOn_integrableOn_of_isClosed_hasCompactSupport
    {X : Type*} [TopologicalSpace X] [T2Space X] [MeasurableSpace X] [BorelSpace X]
    {μ : MeasureTheory.Measure X} [IsFiniteMeasureOnCompacts μ]
    {E : Type*} [NormedAddCommGroup E]
    {g : X → E} {C : Set X}
    (hg : ContinuousOn g C) (hC : IsClosed C) (hsupp : HasCompactSupport g) :
    MeasureTheory.IntegrableOn g C μ := by
  have hcompact : IsCompact (C ∩ tsupport g) := hsupp.inter_left hC
  have hcont : ContinuousOn g (C ∩ tsupport g) := hg.mono Set.inter_subset_left
  have h1 : IntegrableOn g (C ∩ tsupport g) μ := hcont.integrableOn_compact hcompact
  have h2 : IntegrableOn g (C ∩ Function.support g) μ :=
    h1.mono_set (Set.inter_subset_inter_right C (subset_tsupport g))
  exact h2.of_inter_support hC.measurableSet

/-- The reparametrized integrand `(t, s) ↦ F (s • e₀ + faceEmbedL t)` is continuous on
`univ ×ˢ Ici 0`, given that `F` is continuous on the closed half-space `{y | 0 ≤ y 0}`.
The image of `univ ×ˢ Ici 0` lands in the half-space since the zeroth coordinate of
`Φ (t, s)` equals `s`. -/
theorem reparam_within_continuousOn
    (F : EuclideanSpace ℝ (Fin (n + 1)) → ℝ)
    (hF : ContinuousOn F {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0}) :
    ContinuousOn
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        F (q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1))
      ((Set.univ : Set (EuclideanSpace ℝ (Fin n))) ×ˢ Set.Ici (0 : ℝ)) := by
  have hcont_aff : Continuous
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1) := by fun_prop
  have hmaps : Set.MapsTo
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1)
      ((Set.univ : Set (EuclideanSpace ℝ (Fin n))) ×ˢ Set.Ici (0 : ℝ))
      {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0} := by
    rintro ⟨t, s⟩ hq
    simp only [Set.mem_prod, Set.mem_univ, Set.mem_Ici, true_and] at hq
    have hb : (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0) 0 = 1 := by
      simp [EuclideanSpace.basisFun_apply, EuclideanSpace.single]
    have hf : (faceEmbedL t) 0 = 0 := by
      have key : (EuclideanSpace.proj (0 : Fin (n + 1))) (faceEmbedL (n := n) t) = 0 := by
        simp only [faceEmbedL, ContinuousLinearMap.sum_apply,
          ContinuousLinearMap.smulRight_apply]
        rw [map_sum (EuclideanSpace.proj (0 : Fin (n + 1)))]
        simp only [map_smul]
        apply Finset.sum_eq_zero
        intro i _
        simp only [EuclideanSpace.proj, PiLp.proj, ContinuousLinearMap.coe_mk',
          PiLp.projₗ_apply, EuclideanSpace.basisFun_apply, EuclideanSpace.single,
          PiLp.ofLp_single, Pi.single_apply, (Fin.succ_ne_zero i).symm, ↓reduceIte, smul_zero]
      simpa [EuclideanSpace.proj, PiLp.proj] using key
    simp only [Set.mem_setOf_eq, PiLp.add_apply, PiLp.smul_apply, smul_eq_mul, hb, mul_one,
      hf, add_zero]
    exact hq
  exact hF.comp hcont_aff.continuousOn hmaps

/-- The reparametrized integrand `(t, s) ↦ F (s • e₀ + faceEmbedL t)` is integrable on
`univ ×ˢ Ioi 0` with respect to the product measure, given that `F` is continuous on the
closed half-space `{y | 0 ≤ y 0}` and has compact support. -/
theorem reparam_within_integrableOn_prod
    (F : EuclideanSpace ℝ (Fin (n + 1)) → ℝ)
    (hF : ContinuousOn F {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0})
    (hFsupp : HasCompactSupport F) :
    MeasureTheory.IntegrableOn
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        F (q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1))
      (Set.univ ×ˢ Set.Ioi (0 : ℝ))
      ((MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
        MeasureTheory.volume) := by
  have hcont : ContinuousOn
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        F (q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1))
      ((Set.univ : Set (EuclideanSpace ℝ (Fin n))) ×ˢ Set.Ici (0 : ℝ)) :=
    reparam_within_continuousOn F hF
  have hsupp : HasCompactSupport
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        F (q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1)) :=
    (hFsupp.comp_isClosedEmbedding (reparam_closed_embedding (n := n)))
  have hclosed : IsClosed
      ((Set.univ : Set (EuclideanSpace ℝ (Fin n))) ×ˢ Set.Ici (0 : ℝ)) :=
    isClosed_univ.prod isClosed_Ici
  have hint : MeasureTheory.IntegrableOn
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        F (q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1))
      ((Set.univ : Set (EuclideanSpace ℝ (Fin n))) ×ˢ Set.Ici (0 : ℝ))
      ((MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
        MeasureTheory.volume) :=
    continuousOn_integrableOn_of_isClosed_hasCompactSupport hcont hclosed hsupp
  exact hint.mono_set (Set.prod_mono (subset_refl _) Set.Ioi_subset_Ici_self)

/-- Change of variables for integration over the closed half-space `{y | 0 ≤ y 0}`:
the integral of `F` over the half-space equals the iterated integral of
`(t, x) ↦ F (x • e₀ + faceEmbedL t)` over `EuclideanSpace ℝ (Fin n) × Ioi 0`. -/
theorem halfspace_within_integral_change_var
    (F : EuclideanSpace ℝ (Fin (n + 1)) → ℝ)
    (hF : ContinuousOn F {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0})
    (hFsupp : HasCompactSupport F) :
    (∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0}, F y ∂MeasureTheory.volume)
      = ∫ t : EuclideanSpace ℝ (Fin n),
          (∫ x in Set.Ioi (0 : ℝ),
            F (x • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)
            ∂MeasureTheory.volume) ∂MeasureTheory.volume := by
  have h_integ : MeasureTheory.IntegrableOn
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        F (q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1))
      (Set.univ ×ˢ Set.Ioi (0 : ℝ))
      ((MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
        MeasureTheory.volume) := reparam_within_integrableOn_prod F hF hFsupp
  have h_mp : MeasureTheory.MeasurePreserving
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1)
      ((MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
        MeasureTheory.volume)
      (MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin (n + 1)))) :=
    reparam_measure_preserving
  have h_emb : MeasurableEmbedding
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
        q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1) :=
    reparam_measurable_embedding
  have h_set :
      ((fun q : EuclideanSpace ℝ (Fin n) × ℝ =>
          q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1)
        ⁻¹' {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0})
      =ᵐ[(MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
          MeasureTheory.volume]
      (Set.univ ×ˢ Set.Ioi (0 : ℝ)) := halfspace_preimage_ae_prod
  rw [← h_mp.setIntegral_preimage_emb h_emb F, MeasureTheory.setIntegral_congr_set h_set,
    MeasureTheory.setIntegral_prod _ h_integ, MeasureTheory.setIntegral_univ]

end Library.Geometry.Manifold.HalfspaceIntegralFTC
