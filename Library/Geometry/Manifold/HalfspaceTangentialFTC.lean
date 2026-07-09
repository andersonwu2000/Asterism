import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.HalfspaceIntegralFTC
import Library.Geometry.Manifold.HalfspaceNormalFTC
import Library.Geometry.Manifold.InducedOrientNonzero         -- inducedOrient, inducedOrient_ne_zero
import Library.Geometry.Manifold.OneSidedFTC
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBdry.PullbackBdryDefs         -- pullbackBdryFun
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff    -- contMDiff_pullbackBdryFun
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry
import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.Calculus.ContDiff.WithLp
import Mathlib.Analysis.Calculus.Deriv.Basic
import Mathlib.Analysis.Calculus.Deriv.Comp
import Mathlib.Analysis.Calculus.FDeriv.Basic
import Mathlib.Analysis.Calculus.FDeriv.ContinuousAlternatingMap
import Mathlib.Analysis.Calculus.LineDeriv.Basic
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.Normed.Lp.PiLp
import Mathlib.Analysis.Normed.Operator.LinearIsometry
import Mathlib.Data.Fin.Tuple.Basic
import Mathlib.Logic.Equiv.Basic
import Mathlib.MeasureTheory.Constructions.BorelSpace.Order
import Mathlib.MeasureTheory.Integral.Bochner.FundThmCalculus
import Mathlib.MeasureTheory.Integral.Bochner.Set
import Mathlib.MeasureTheory.Integral.IntegrableOn
import Mathlib.MeasureTheory.Integral.Prod
import Mathlib.MeasureTheory.MeasurableSpace.Embedding
import Mathlib.MeasureTheory.Measure.Haar.InnerProductSpace
import Mathlib.MeasureTheory.Measure.MeasureSpace
import Mathlib.MeasureTheory.SpecificCodomains.WithLp
import Mathlib.Topology.Algebra.Module.Basic
import Mathlib.Topology.Algebra.Module.FiniteDimension
import Mathlib.Topology.Algebra.Support
import Mathlib.Topology.Homeomorph.Lemmas
import Mathlib.Topology.Order.Basic

/-!
# Tangential half-space FTC

This file establishes that the half-space integral of a tangential directional derivative
(along any basis direction `eₖ` with `k ≠ 0`) vanishes, for differential forms that are
smooth on the half-space `{y | 0 ≤ y 0}` and have compact support. The result is combined
with the normal FTC to obtain the full half-space divergence theorem in coordinates.

## Main statements

- `halfspace_tangential_linederiv_integral_zero_on`: the half-space integral of
  `lineDeriv ℝ (w · tuple) y (single k 1)` is zero for `k ≠ 0`.
- `halfspace_tangential_fderivwithin_integral_zero_on`: the same with `fderivWithin`
  in place of `lineDeriv` (with scalar factor `(-1)^k`).
- `halfspace_topcoeff_extderiv_eq_neg_face_on`: the half-space integral of
  `topCoeff (extDerivWithin w …)` equals the negated face integral, proving the
  coordinate-level FTC for forms smooth on the half-space.
-/

open Bundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.HalfspaceIntegralFTC
open Library.Geometry.Manifold.HalfspaceNormalFTC
open Library.Geometry.Manifold.InducedOrientNonzero
open Library.Geometry.Manifold.OneSidedFTC
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open MeasureTheory
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.HalfspaceTangentialFTC

/-- The preimage of the half-space `{y | 0 ≤ y 0}` under the tangential reparametrisation
`(t, x) ↦ x • single i 1 + σ (faceEmbedL t)` (where `σ = piLpCongrLeft (swap 0 i)`)
equals, almost everywhere, the product set `S ×ˢ Set.univ`, where
`S = {t | 0 ≤ (σ (faceEmbedL t)) 0}`.
This equality holds exactly (not merely a.e.), witnessed by a set-extensionality argument. -/
theorem tangential_halfspace_preimage_ae_prod {n : ℕ}
    (i : Fin (n + 1)) (hi : i ≠ 0) :
    ((fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        q.2 • EuclideanSpace.single i 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
            (faceEmbedL q.1))
      ⁻¹' {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0})
      =ᵐ[(MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
          MeasureTheory.volume]
      ({t : EuclideanSpace ℝ (Fin n) |
            0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
                  (faceEmbedL t)) 0} ×ˢ (Set.univ : Set ℝ)) := by
  have hset : ((fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        q.2 • EuclideanSpace.single i 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
            (faceEmbedL q.1))
      ⁻¹' {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0})
      =
      ({t : EuclideanSpace ℝ (Fin n) |
            0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
                  (faceEmbedL t)) 0} ×ˢ (Set.univ : Set ℝ)) := by
    ext q
    simp only [Set.mem_preimage, Set.mem_setOf_eq, Set.mem_prod, Set.mem_univ, and_true,
      PiLp.add_apply, PiLp.smul_apply, PiLp.single_apply, smul_eq_mul]
    rw [if_neg (Ne.symm hi)]
    ring_nf
  rw [hset]

/-- The tangential reparametrisation `(t, x) ↦ x • single i 1 + σ (faceEmbedL t)` is
injective, where `σ = piLpCongrLeft (swap 0 i)`.
This follows by expressing the map as `σ ∘ Φ₀` where
`Φ₀ (t, x) = x • basisFun 0 + faceEmbedL t` is the proved coord-0 reparametrisation,
and using `σ.injective.comp reparam_injective`. -/
theorem tangential_reparam_injective {n : ℕ} (i : Fin (n + 1)) :
    Function.Injective
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        q.2 • EuclideanSpace.single i 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
            (faceEmbedL q.1)) := by
  have hfun : (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        q.2 • EuclideanSpace.single i 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
            (faceEmbedL q.1)) =
      (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)) ∘
        (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
          q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1) := by
    funext q
    simp only [Function.comp_apply, map_add, map_smul, EuclideanSpace.basisFun_apply,
      EuclideanSpace.piLpCongrLeft_single, Equiv.swap_apply_left]
  rw [hfun]
  exact (LinearIsometryEquiv.injective _).comp reparam_injective

/-- The tangential reparametrisation `(t, x) ↦ x • single i 1 + σ (faceEmbedL t)` is a
closed embedding. The map is linear (packaged as a `ContinuousLinearMap`), and an injective
linear map between finite-dimensional spaces is a closed embedding. -/
theorem tangential_reparam_closed_embedding {n : ℕ} (i : Fin (n + 1)) :
    Topology.IsClosedEmbedding
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        q.2 • EuclideanSpace.single i 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
            (faceEmbedL q.1)) := by
  have hinj := tangential_reparam_injective (n := n) i
  set σ := LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i) with hσ
  set ei : EuclideanSpace ℝ (Fin (n + 1)) := EuclideanSpace.single i 1 with hei
  let L : (EuclideanSpace ℝ (Fin n) × ℝ) →L[ℝ] EuclideanSpace ℝ (Fin (n + 1)) :=
    (ContinuousLinearMap.snd ℝ (EuclideanSpace ℝ (Fin n)) ℝ).smulRight ei +
      (σ.toContinuousLinearEquiv.toContinuousLinearMap.comp faceEmbedL).comp
        (ContinuousLinearMap.fst ℝ (EuclideanSpace ℝ (Fin n)) ℝ)
  have hL : (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦ q.2 • ei + σ (faceEmbedL q.1)) = ⇑L := by
    funext q
    simp [L]
  rw [hL]
  rw [hL] at hinj
  exact LinearMap.isClosedEmbedding_of_injective
    (f := L.toLinearMap) (LinearMap.ker_eq_bot.mpr hinj)

/-- The tangential reparametrisation `(t, x) ↦ x • single i 1 + σ (faceEmbedL t)` is a
measurable embedding. It factors as `σ ∘ Φ₀` where `σ = piLpCongrLeft (swap 0 i)` is a
`LinearIsometryEquiv` (hence a measurable embedding) and `Φ₀` is the proved coord-0
reparametrisation `reparam_measurable_embedding`. -/
theorem tangential_reparam_measurable_embedding {n : ℕ}
    (i : Fin (n + 1)) (hi : i ≠ 0) :
    MeasurableEmbedding
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        q.2 • EuclideanSpace.single i 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
            (faceEmbedL q.1)) := by
  have h0 : MeasurableEmbedding (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
      q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1) :=
    reparam_measurable_embedding
  have hσ : MeasurableEmbedding
      (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)) :=
    (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ
      (Equiv.swap (0 : Fin (n + 1)) i)).toHomeomorph.measurableEmbedding
  have heq : (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        q.2 • EuclideanSpace.single i 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
            (faceEmbedL q.1))
      = (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)) ∘
          (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
            q.2 • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL q.1) := by
    funext q
    simp only [Function.comp_apply, map_add, map_smul, EuclideanSpace.basisFun_apply,
      EuclideanSpace.piLpCongrLeft_single, Equiv.swap_apply_left]
  rw [heq]
  exact hσ.comp h0

/-- The tangential reparametrisation `(t, x) ↦ x • single i 1 + σ (faceEmbedL t)` is
measure-preserving from `volume.prod volume` to `volume`. It factors as `σ ∘ Φ₀` where
`σ = piLpCongrLeft (swap 0 i)` preserves measure as a `LinearIsometryEquiv`, and `Φ₀`
is the proved coord-0 reparametrisation `reparam_measure_preserving`. -/
theorem tangential_reparam_measure_preserving {n : ℕ}
    (i : Fin (n + 1)) (hi : i ≠ 0) :
    MeasureTheory.MeasurePreserving
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        q.2 • EuclideanSpace.single i 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
            (faceEmbedL q.1))
      ((MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
        MeasureTheory.volume)
      (MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin (n + 1)))) := by
  have hphi := reparam_measure_preserving (n := n)
  have hsigma :=
    (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)).measurePreserving
  have hcomp := hsigma.comp hphi
  convert hcomp using 1
  funext q
  simp only [Function.comp_apply, map_add, map_smul, EuclideanSpace.basisFun_apply,
    EuclideanSpace.piLpCongrLeft_single, Equiv.swap_apply_left]

/-- Change of variables for the half-space integral of a tangential `lineDeriv`: the integral
over `{y | 0 ≤ y 0}` equals the integral over the product set `S ×ˢ Set.univ` under the
swap reparametrisation, where `S = {t | 0 ≤ (σ (faceEmbedL t)) 0}`. No smoothness on `g`
is needed; only the measure-preserving and measurable-embedding properties are used. -/
theorem reparam_to_prod_generic {n : ℕ}
    (g : EuclideanSpace ℝ (Fin (n + 1)) → ℝ)
    (i : Fin (n + 1)) (hi : i ≠ 0) :
    ∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
        lineDeriv ℝ g y (EuclideanSpace.single i 1) ∂MeasureTheory.volume
      = ∫ q in {t : EuclideanSpace ℝ (Fin n) |
            0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
                  (faceEmbedL t)) 0} ×ˢ (Set.univ : Set ℝ),
          lineDeriv ℝ g
            (q.2 • EuclideanSpace.single i 1 +
              LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
                (faceEmbedL q.1))
            (EuclideanSpace.single i 1)
          ∂((MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
              MeasureTheory.volume) := by
  have h_mp : MeasureTheory.MeasurePreserving
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        q.2 • EuclideanSpace.single i 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
            (faceEmbedL q.1))
      ((MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
        MeasureTheory.volume)
      (MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin (n + 1)))) :=
    tangential_reparam_measure_preserving i hi
  have h_emb : MeasurableEmbedding
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        q.2 • EuclideanSpace.single i 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
            (faceEmbedL q.1)) :=
    tangential_reparam_measurable_embedding i hi
  have h_set :
      ((fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
          q.2 • EuclideanSpace.single i 1 +
            LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
              (faceEmbedL q.1))
        ⁻¹' {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0})
      =ᵐ[(MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
          MeasureTheory.volume]
      ({t : EuclideanSpace ℝ (Fin n) |
            0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
                  (faceEmbedL t)) 0} ×ˢ (Set.univ : Set ℝ)) :=
    tangential_halfspace_preimage_ae_prod i hi
  rw [← h_mp.setIntegral_preimage_emb h_emb
      (fun y ↦ lineDeriv ℝ g y (EuclideanSpace.single i 1))]
  exact MeasureTheory.setIntegral_congr_set h_set

/-- Fubini for the `S ×ˢ Set.univ` integral: peels off the iterated integral via
`setIntegral_prod` given an integrability hypothesis, then drops `in Set.univ`
via `setIntegral_univ`. -/
theorem prod_fubini_to_iterated_generic {n : ℕ}
    (g : EuclideanSpace ℝ (Fin (n + 1)) → ℝ)
    (i : Fin (n + 1)) (hi : i ≠ 0)
    (h_integ : MeasureTheory.IntegrableOn
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        lineDeriv ℝ g
          (q.2 • EuclideanSpace.single i 1 +
            LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
              (faceEmbedL q.1))
          (EuclideanSpace.single i 1))
      ({t : EuclideanSpace ℝ (Fin n) |
            0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
                  (faceEmbedL t)) 0} ×ˢ (Set.univ : Set ℝ))
      ((MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
          MeasureTheory.volume)) :
    (∫ q in {t : EuclideanSpace ℝ (Fin n) |
            0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
                  (faceEmbedL t)) 0} ×ˢ (Set.univ : Set ℝ),
          lineDeriv ℝ g
            (q.2 • EuclideanSpace.single i 1 +
              LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
                (faceEmbedL q.1))
            (EuclideanSpace.single i 1)
          ∂((MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
              MeasureTheory.volume))
      = ∫ t in {t : EuclideanSpace ℝ (Fin n) |
            0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
                  (faceEmbedL t)) 0},
          (∫ x : ℝ,
            lineDeriv ℝ g
              (x • EuclideanSpace.single i 1 +
                LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) i)
                  (faceEmbedL t))
              (EuclideanSpace.single i 1) ∂MeasureTheory.volume)
      ∂MeasureTheory.volume := by
  rw [MeasureTheory.setIntegral_prod _ h_integ]
  simp only [MeasureTheory.setIntegral_univ]

/-- Evaluation of an alternating map `w z` at a fixed tuple `m` inherits compact support from
`w`: the support of `z ↦ w z m` is contained in the support of `w`, since `w z = 0` implies
`w z m = 0`. -/
theorem alternating_apply_hascompactsupport {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hwsupp : HasCompactSupport w)
    (m : Fin n → EuclideanSpace ℝ (Fin (n + 1))) :
    HasCompactSupport (fun z ↦ w z m) := by
  apply hwsupp.mono
  intro z hz
  simp only [Function.mem_support] at hz ⊢
  intro h
  exact hz (by rw [h]; simp)

/-- The directional derivative `lineDeriv ℝ g y v` has compact support in `y` when `g` has
compact support. This follows because outside `tsupport g` the function `g` is locally
zero, making the one-variable function `t ↦ g (y + t • v)` eventually zero near `t = 0`,
so its derivative at `0` vanishes. -/
theorem line_deriv_hascompactsupport {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    (g : E → ℝ) (hsupp : HasCompactSupport g) (v : E) :
    HasCompactSupport (fun y ↦ lineDeriv ℝ g y v) := by
  apply hsupp.mono'
  intro y hy
  simp only [Function.mem_support] at hy
  by_contra hy'
  apply hy
  simp only [lineDeriv]
  have hg : g =ᶠ[nhds y] 0 := notMem_tsupport_iff_eventuallyEq.mp hy'
  have hcts : Continuous (fun t : ℝ ↦ y + t • v) := by fun_prop
  have hline : (fun t ↦ g (y + t • v)) =ᶠ[nhds (0 : ℝ)] fun _ ↦ (0 : ℝ) := by
    have htend : Filter.Tendsto (fun t : ℝ ↦ y + t • v) (nhds 0) (nhds y) := by
      convert hcts.tendsto 0 using 1
      simp
    exact hg.comp_tendsto htend
  rw [hline.deriv_eq]
  simp [deriv_const]

/-- The reparametrised tangential integrand `(t, x) ↦ lineDeriv ℝ (w · tuple) (x • eₖ + σ t) eₖ`
has compact support, where `tuple = k.removeNth basisFun` and `σ = piLpCongrLeft (swap 0 k)`.
Compact support of `w · tuple` follows from `alternating_apply_hascompactsupport`, then
`line_deriv_hascompactsupport` gives compact support of the directional derivative, and
`HasCompactSupport.comp_isClosedEmbedding` transfers it through the reparametrisation. -/
theorem tangential_reparam_compact_support_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hwsupp : HasCompactSupport w)
    (k : Fin (n + 1)) :
    HasCompactSupport
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        lineDeriv ℝ (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
          (q.2 • EuclideanSpace.single k 1 +
            LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
              (faceEmbedL q.1))
          (EuclideanSpace.single k 1)) := by
  have hg : HasCompactSupport
      (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) :=
    alternating_apply_hascompactsupport w hwsupp
      (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))
  have h_F : HasCompactSupport
      (fun y ↦ lineDeriv ℝ
        (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) y
        (EuclideanSpace.single k 1)) :=
    line_deriv_hascompactsupport _ hg (EuclideanSpace.single k 1)
  have h_emb : Topology.IsClosedEmbedding
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        q.2 • EuclideanSpace.single k 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
            (faceEmbedL q.1)) :=
    tangential_reparam_closed_embedding k
  exact h_F.comp_isClosedEmbedding h_emb

/-- The integral of `lineDeriv ℝ g (x • eₖ + c) eₖ` over `x : ℝ` equals the integral of the
derivative of the slice `u ↦ g (u • eₖ + c)`. The identity follows from the chain rule:
`lineDeriv ℝ g (x • eₖ + c) eₖ = deriv (fun u => g (u • eₖ + c)) x`. -/
theorem tangential_line_deriv_integral_eq_slice {n : ℕ}
    (g : EuclideanSpace ℝ (Fin (n + 1)) → ℝ) (k : Fin (n + 1))
    (c : EuclideanSpace ℝ (Fin (n + 1)))
    (hdiff : Differentiable ℝ (fun u : ℝ ↦ g (u • EuclideanSpace.single k 1 + c))) :
    (∫ x : ℝ, lineDeriv ℝ g (x • EuclideanSpace.single k 1 + c)
        (EuclideanSpace.single k 1) ∂MeasureTheory.volume)
      = ∫ x : ℝ, deriv (fun u : ℝ ↦ g (u • EuclideanSpace.single k 1 + c)) x
        ∂MeasureTheory.volume := by
  congr 1; ext x
  simp only [lineDeriv]
  have heq : (fun t : ℝ ↦
        g (x • EuclideanSpace.single k 1 + c + t • EuclideanSpace.single k 1)) =
      fun t : ℝ ↦ g ((x + t) • EuclideanSpace.single k 1 + c) := by
    ext t; simp [add_smul, add_comm, add_assoc]
  rw [heq]
  have hslice_at : HasDerivAt (fun u : ℝ ↦ g (u • EuclideanSpace.single k 1 + c))
      (deriv (fun u : ℝ ↦ g (u • EuclideanSpace.single k 1 + c)) x) (x + 0) := by
    simp only [add_zero]; exact (hdiff x).hasDerivAt
  have hshift : HasDerivAt (fun t : ℝ ↦ x + t) 1 0 :=
    (hasDerivAt_id (0 : ℝ)).const_add x
  have hcomp := hslice_at.comp 0 hshift
  simp only [mul_one] at hcomp
  exact hcomp.deriv

/-- The scalar slice `u ↦ w (u • eₖ + c) tuple` has compact support. The affine embedding
`u ↦ u • eₖ + c` is a closed embedding (composition of scalar-smul and translation
homeomorphisms), and the support inclusion
`support (fun u => w (u • eₖ + c) tuple) ⊆ support (fun u => w (u • eₖ + c))`
transfers compact support from `w` through the evaluation at `tuple`. -/
theorem tangential_slice_compact_support {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hwsupp : HasCompactSupport w)
    (k : Fin (n + 1)) (c : EuclideanSpace ℝ (Fin (n + 1))) :
    HasCompactSupport (fun u : ℝ ↦
      w (u • EuclideanSpace.single k 1 + c)
        (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) := by
  have h1 : HasCompactSupport (fun u : ℝ ↦ w (u • EuclideanSpace.single k 1 + c)) := by
    apply hwsupp.comp_isClosedEmbedding
    apply (Homeomorph.addRight c).isClosedEmbedding.comp
    exact isClosedEmbedding_smul_left ((PiLp.single_eq_zero_iff 2 k).not.mpr one_ne_zero)
  have h2 : Function.support (fun u : ℝ ↦ w (u • EuclideanSpace.single k 1 + c)
      (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) ⊆
      Function.support (fun u : ℝ ↦ w (u • EuclideanSpace.single k 1 + c)) := by
    intro u hu
    simp only [Function.mem_support] at hu ⊢
    intro hw
    exact hu (by rw [hw]; simp)
  exact h1.mono h2

/-- The scalar slice `u ↦ w (u • eₖ + c) tuple` is `C¹` when `k ≠ 0` and `0 ≤ c 0`.
Since `k ≠ 0`, moving along `eₖ` leaves coordinate `0` fixed at `c 0 ≥ 0`, so every
point `u • eₖ + c` lies in `range 𝓡∂ = {y | 0 ≤ y 0}` where `w` is `C^∞`. -/
theorem tangential_slice_contdiff {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1))))
    (k : Fin (n + 1)) (hk : k ≠ 0)
    (c : EuclideanSpace ℝ (Fin (n + 1))) (hc0 : 0 ≤ c 0) :
    ContDiff ℝ 1 (fun u : ℝ ↦
      w (u • EuclideanSpace.single k 1 + c)
        (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) := by
  set tuple := k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ) with htuple
  have hline : ContDiff ℝ ∞ (fun u : ℝ ↦ u • EuclideanSpace.single k 1 + c) := by fun_prop
  have hmaps : ∀ u : ℝ, (u • EuclideanSpace.single k 1 + c) ∈ Set.range (𝓡∂ (n + 1)) := by
    intro u
    rw [range_modelWithCornersEuclideanHalfSpace]
    simp only [Set.mem_setOf_eq, PiLp.add_apply, PiLp.smul_apply, EuclideanSpace.single_apply,
      smul_eq_mul]
    rw [if_neg (fun h => hk h.symm)]
    simpa using hc0
  have heval : ContDiffOn ℝ ∞ (fun z ↦ w z tuple) (Set.range (𝓡∂ (n + 1))) :=
    (ContinuousAlternatingMap.apply ℝ _ ℝ tuple).contDiff.comp_contDiffOn hw
  exact (heval.comp_contDiff hline hmaps).of_le (by exact_mod_cast le_top)

/-- For each `t` in the constraint set `S = {t | 0 ≤ (σ (faceEmbedL t)) 0}`, the full-line
integral of `lineDeriv ℝ (w · tuple) (x • eₖ + c) eₖ` over `x : ℝ` vanishes, where
`c = σ (faceEmbedL t)`.
Since `k ≠ 0`, the line `x • eₖ + c` stays in `{y₀ ≥ 0} = range 𝓡∂`, so the slice is
globally `C¹` (via `tangential_slice_contdiff`) and has compact support. The fundamental
theorem of calculus for compactly supported functions then gives zero. -/
theorem tangential_constrained_slice_integral_zero_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w)
    (k : Fin (n + 1)) (hk : k ≠ 0) :
    ∀ t ∈ {t : EuclideanSpace ℝ (Fin n) |
          0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
                (faceEmbedL t)) 0},
        (∫ x : ℝ,
          lineDeriv ℝ (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
            (x • EuclideanSpace.single k 1 +
              LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
                (faceEmbedL t))
            (EuclideanSpace.single k 1) ∂MeasureTheory.volume) = 0 := by
  intro t ht
  set g : EuclideanSpace ℝ (Fin (n + 1)) → ℝ :=
    fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)) with hg_def
  set c : EuclideanSpace ℝ (Fin (n + 1)) :=
    LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k) (faceEmbedL t)
    with hc_def
  have hc0 : 0 ≤ c 0 := ht
  have h_cd : ContDiff ℝ 1 (fun u : ℝ ↦ g (u • EuclideanSpace.single k 1 + c)) :=
    tangential_slice_contdiff w hw k hk c hc0
  have h_cs : HasCompactSupport (fun u : ℝ ↦ g (u • EuclideanSpace.single k 1 + c)) :=
    tangential_slice_compact_support w hwsupp k c
  have h_eq : (∫ x : ℝ, lineDeriv ℝ g (x • EuclideanSpace.single k 1 + c)
        (EuclideanSpace.single k 1) ∂MeasureTheory.volume)
      = ∫ x : ℝ, deriv (fun u : ℝ ↦ g (u • EuclideanSpace.single k 1 + c)) x
        ∂MeasureTheory.volume :=
    tangential_line_deriv_integral_eq_slice g k c (h_cd.differentiable one_ne_zero)
  rw [h_eq]
  exact integral_deriv_eq_zero_of_hasCompactSupport _ h_cd h_cs

/-- The outer set-integral over the constraint set `S = {t | 0 ≤ (σ (faceEmbedL t)) 0}` of
the inner full-line `lineDeriv` integral vanishes. For each `t ∈ S` the inner integral is
zero (by `tangential_constrained_slice_integral_zero_on`), so the outer integral of a
pointwise-zero function is zero. -/
theorem tangential_reparam_outer_integral_zero_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w)
    (k : Fin (n + 1)) (hk : k ≠ 0) :
    ∫ t in {t : EuclideanSpace ℝ (Fin n) |
          0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
                (faceEmbedL t)) 0},
        (∫ x : ℝ,
          lineDeriv ℝ (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
            (x • EuclideanSpace.single k 1 +
              LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
                (faceEmbedL t))
            (EuclideanSpace.single k 1) ∂MeasureTheory.volume)
        ∂MeasureTheory.volume = 0 := by
  have h_slice := tangential_constrained_slice_integral_zero_on w hw hwsupp k hk
  exact MeasureTheory.setIntegral_eq_zero_of_forall_eq_zero h_slice

/-- Pointwise expansion of `topCoeff (extDerivWithin w (range 𝓡∂) y)` on the half-space,
when `w` is `ContDiffOn ℝ ∞` on `range 𝓡∂`. The identity expresses the top coefficient as
`∑ᵢ (-1)^i • fderivWithin ℝ (w · (i.removeNth basisFun)) (range 𝓡∂) y (basisFun i)`,
following from `extDerivWithin_apply`. -/
theorem topcoeff_extderiv_expand_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) :
    ∀ y ∈ {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
      topCoeff (extDerivWithin w (Set.range (𝓡∂ (n + 1))) y)
        = ∑ i : Fin (n + 1),
            ((-1 : ℝ)) ^ (i : ℕ) •
              fderivWithin ℝ
                (fun z ↦ w z (i.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
                (Set.range (𝓡∂ (n + 1))) y
                (EuclideanSpace.basisFun (Fin (n + 1)) ℝ i) := by
  intro y hy
  simp only [topCoeff]
  have hyr : y ∈ Set.range (𝓡∂ (n + 1)) := by
    rw [range_modelWithCornersEuclideanHalfSpace]; exact hy
  have hdiff : DifferentiableWithinAt ℝ w (Set.range (𝓡∂ (n + 1))) y :=
    (hw y hyr).differentiableWithinAt (by norm_num)
  have huniq : UniqueDiffWithinAt ℝ (Set.range (𝓡∂ (n + 1))) y :=
    (𝓡∂ (n + 1)).uniqueDiffOn y (by rw [range_modelWithCornersEuclideanHalfSpace]; exact hy)
  have key := extDerivWithin_apply hdiff huniq (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)
  simp only [← Int.cast_smul_eq_zsmul ℝ, Int.cast_pow, Int.cast_neg, Int.cast_one] at key
  exact key

/-- Pointwise expansion of `topCoeff (extDerivWithin w (range 𝓡∂) y)` when `w` is globally
`ContDiff ℝ ∞`. The identity is the same as `topcoeff_extderiv_expand_on` but the
differentiability hypothesis is derived from the global smoothness assumption. -/
theorem topcoeff_extderiv_pointwise_expand {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiff ℝ ∞ w) :
    ∀ y ∈ {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
      topCoeff (extDerivWithin w (Set.range (𝓡∂ (n + 1))) y)
        = ∑ i : Fin (n + 1),
            ((-1 : ℝ)) ^ (i : ℕ) •
              fderivWithin ℝ
                (fun z ↦ w z (i.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
                (Set.range (𝓡∂ (n + 1))) y
                (EuclideanSpace.basisFun (Fin (n + 1)) ℝ i) := by
  intro y hy
  simp only [topCoeff]
  have hdiff : DifferentiableWithinAt ℝ w (Set.range (𝓡∂ (n + 1))) y :=
    hw.differentiable (by norm_num) |>.differentiableAt.differentiableWithinAt
  have huniq : UniqueDiffWithinAt ℝ (Set.range (𝓡∂ (n + 1))) y :=
    (𝓡∂ (n + 1)).uniqueDiffOn y (by rw [range_modelWithCornersEuclideanHalfSpace]; exact hy)
  have key := extDerivWithin_apply hdiff huniq (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)
  simp only [← Int.cast_smul_eq_zsmul ℝ, Int.cast_pow, Int.cast_neg, Int.cast_one] at key
  exact key

/-- The half-space integral of `topCoeff (extDerivWithin w …)` equals the half-space integral
of the divergence sum `∑ᵢ (-1)^i • fderivWithin ℝ (w · (i.removeNth basisFun)) … (basisFun i)`,
for globally smooth `w`. Follows from `setIntegral_congr_fun` applied to the pointwise
expansion `topcoeff_extderiv_pointwise_expand`. -/
theorem halfspace_topcoeff_extderiv_integral_expand {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n+1)) → EuclideanSpace ℝ (Fin (n+1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiff ℝ ∞ w) :
    ∫ y in {y : EuclideanSpace ℝ (Fin (n+1)) | 0 ≤ y 0},
        topCoeff (extDerivWithin w (Set.range (𝓡∂ (n+1))) y) ∂MeasureTheory.volume
      = ∫ y in {y : EuclideanSpace ℝ (Fin (n+1)) | 0 ≤ y 0},
          (∑ i : Fin (n+1),
            ((-1 : ℝ)) ^ (i : ℕ) •
              fderivWithin ℝ
                (fun z ↦ w z (i.removeNth (EuclideanSpace.basisFun (Fin (n+1)) ℝ)))
                (Set.range (𝓡∂ (n+1))) y
          (EuclideanSpace.basisFun (Fin (n+1)) ℝ i)) ∂MeasureTheory.volume := by
  have h_meas := measurableSet_halfspace_zero_coord (n := n)
  have h_pointwise := topcoeff_extderiv_pointwise_expand w hw
  exact setIntegral_congr_fun h_meas h_pointwise

/-- For a tangential direction `k ≠ 0` and a point `y` with `0 ≤ y 0`, the within-derivative
`fderivWithin ℝ (w · tuple) (range 𝓡∂) y (basisFun k)` equals the line derivative
`lineDeriv ℝ (w · tuple) y (single k 1)`.
Since `k ≠ 0`, moving along `eₖ` keeps coordinate `0` fixed at `y 0 ≥ 0`, so the
`eₖ`-line stays in `range 𝓡∂`. This allows passing from within-derivative to full
line derivative via `HasFDerivWithinAt.hasLineDerivAt'`. -/
theorem tangential_fderivwithin_eq_linederiv {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1))))
    (k : Fin (n + 1)) (hk : k ≠ 0)
    (y : EuclideanSpace ℝ (Fin (n + 1))) (hy : 0 ≤ y 0) :
    fderivWithin ℝ (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
        (Set.range (𝓡∂ (n + 1))) y (EuclideanSpace.basisFun (Fin (n + 1)) ℝ k)
      = lineDeriv ℝ (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) y
          (EuclideanSpace.single k 1) := by
  rw [EuclideanSpace.basisFun_apply]
  have hcd : ContDiffOn ℝ ∞
      (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
      (Set.range (𝓡∂ (n + 1))) := by
    let L := ContinuousAlternatingMap.apply ℝ (EuclideanSpace ℝ (Fin (n + 1))) ℝ
      (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))
    apply ContDiffOn.comp L.contDiff.contDiffOn hw
    exact Set.mapsTo_univ _ _
  have hy' : y ∈ Set.range (𝓡∂ (n + 1)) := by
    rw [range_modelWithCornersEuclideanHalfSpace]; exact hy
  have hdiff : DifferentiableWithinAt ℝ
      (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
      (Set.range (𝓡∂ (n + 1))) y :=
    (hcd.differentiableOn (by norm_num)) y hy'
  have hfd := hdiff.hasFDerivWithinAt
  have hlw := hfd.hasLineDerivWithinAt (EuclideanSpace.single k 1)
  have hmem : ∀ᶠ t : ℝ in nhds 0,
      y + t • (EuclideanSpace.single k 1 : EuclideanSpace ℝ (Fin (n + 1)))
        ∈ Set.range (𝓡∂ (n + 1)) := by
    filter_upwards with t
    rw [range_modelWithCornersEuclideanHalfSpace, Set.mem_setOf_eq]
    have hz : (EuclideanSpace.single k (1:ℝ)) 0 = 0 := by
      rw [EuclideanSpace.single_apply]; exact if_neg (Ne.symm hk)
    simp only [PiLp.add_apply, PiLp.smul_apply, smul_eq_mul, hz, mul_zero, add_zero]
    exact hy
  have hla := hlw.hasLineDerivAt' hmem
  exact hla.lineDeriv.symm

/-- The reparametrised tangential `lineDeriv` integrand is continuous on the product set
`S ×ˢ Set.univ`, where `S = {t | 0 ≤ (σ (faceEmbedL t)) 0}` and `k ≠ 0`.
On `S` the `eₖ`-line keeps coordinate `0 ≥ 0`, so the integrand equals the `fderivWithin`
form (via `tangential_fderivwithin_eq_linederiv`), which is continuous as a composition of
the continuous `fderivWithin` on the half-space with the continuous affine reparametrisation. -/
theorem tangential_reparam_continuous_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1))))
    (k : Fin (n + 1)) (hk : k ≠ 0) :
    ContinuousOn
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        lineDeriv ℝ (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
          (q.2 • EuclideanSpace.single k 1 +
            LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
              (faceEmbedL q.1))
          (EuclideanSpace.single k 1))
      ({t : EuclideanSpace ℝ (Fin n) |
            0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
                  (faceEmbedL t)) 0} ×ˢ (Set.univ : Set ℝ)) := by
  have hterm : ContinuousOn
      (fun y : EuclideanSpace ℝ (Fin (n + 1)) ↦
        fderivWithin ℝ
          (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
          (Set.range (𝓡∂ (n + 1))) y (EuclideanSpace.basisFun (Fin (n + 1)) ℝ k))
      {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0} := by
    rw [show {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0}
        = Set.range (𝓡∂ (n + 1)) from (range_modelWithCornersEuclideanHalfSpace (n + 1)).symm]
    have hg : ContDiffOn ℝ ∞
        (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
        (Set.range (𝓡∂ (n + 1))) :=
      (ContinuousAlternatingMap.apply ℝ _ ℝ
        (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))).contDiff.comp_contDiffOn hw
    exact (hg.continuousOn_fderivWithin (𝓡∂ (n + 1)).uniqueDiffOn (by norm_num)).clm_apply
      continuousOn_const
  have hcont_aff : Continuous
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        q.2 • EuclideanSpace.single k 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
            (faceEmbedL q.1)) := by fun_prop
  have hmaps : Set.MapsTo
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        q.2 • EuclideanSpace.single k 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
            (faceEmbedL q.1))
      ({t : EuclideanSpace ℝ (Fin n) |
            0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
                  (faceEmbedL t)) 0} ×ˢ (Set.univ : Set ℝ))
      {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0} := by
    rintro ⟨t, s⟩ hq
    simp only [Set.mem_prod, Set.mem_setOf_eq, Set.mem_univ, and_true] at hq
    have hz : (EuclideanSpace.single k (1:ℝ)) 0 = 0 := by
      rw [EuclideanSpace.single_apply]; exact if_neg (Ne.symm hk)
    simp only [Set.mem_setOf_eq, PiLp.add_apply, PiLp.smul_apply, smul_eq_mul, hz,
      mul_zero, zero_add]
    exact hq
  refine (hterm.comp hcont_aff.continuousOn hmaps).congr (fun q hq ↦ ?_)
  exact (tangential_fderivwithin_eq_linederiv w hw k hk _ (hmaps hq)).symm

/-- The reparametrised tangential `lineDeriv` integrand is integrable on the product set
`S ×ˢ Set.univ`, where `S = {t | 0 ≤ (σ (faceEmbedL t)) 0}`.
Integrability follows from continuity on the closed set `S ×ˢ Set.univ` combined with
compact support of the integrand (through `hsupp_f.integrableOn_compact_subset`). -/
theorem prod_integrable_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w)
    (k : Fin (n + 1)) (hk : k ≠ 0) :
    MeasureTheory.IntegrableOn
      (fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
        lineDeriv ℝ (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
          (q.2 • EuclideanSpace.single k 1 +
            LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
              (faceEmbedL q.1))
          (EuclideanSpace.single k 1))
      ({t : EuclideanSpace ℝ (Fin n) |
            0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
                  (faceEmbedL t)) 0} ×ˢ (Set.univ : Set ℝ))
      ((MeasureTheory.volume : MeasureTheory.Measure (EuclideanSpace ℝ (Fin n))).prod
          MeasureTheory.volume) := by
  set f : EuclideanSpace ℝ (Fin n) × ℝ → ℝ :=
    fun q : EuclideanSpace ℝ (Fin n) × ℝ ↦
      lineDeriv ℝ (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
        (q.2 • EuclideanSpace.single k 1 +
          LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
            (faceEmbedL q.1))
        (EuclideanSpace.single k 1) with hf_def
  set S : Set (EuclideanSpace ℝ (Fin n)) :=
    {t : EuclideanSpace ℝ (Fin n) |
      0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
            (faceEmbedL t)) 0} with hS_def
  have hcont : ContinuousOn f (S ×ˢ (Set.univ : Set ℝ)) :=
    tangential_reparam_continuous_on w hw k hk
  have hsupp_f : HasCompactSupport f :=
    tangential_reparam_compact_support_on w hwsupp k
  have hSclosed : IsClosed (S ×ˢ (Set.univ : Set ℝ)) :=
    (isClosed_le continuous_const (by fun_prop)).prod isClosed_univ
  have hSmeas : MeasurableSet (S ×ˢ (Set.univ : Set ℝ)) := hSclosed.measurableSet
  have hLI := hcont.locallyIntegrableOn
    (μ := (MeasureTheory.volume).prod MeasureTheory.volume) hSmeas
  apply MeasureTheory.IntegrableOn.of_inter_support hSmeas
  refine (hLI.integrableOn_compact_subset Set.inter_subset_left
    (IsCompact.inter_left hsupp_f hSclosed)).mono_set ?_
  exact Set.inter_subset_inter_right _ (subset_tsupport f)

/-- Half-space `ContDiffOn` analogue of the swap-reparametrisation + Fubini identity:
the half-space integral of `lineDeriv ℝ (w · tuple) y (single k 1)` equals the iterated
integral obtained by the swap reparametrisation and Fubini's theorem.
The reparametrisation and Fubini steps use no smoothness on `g`; all `ContDiffOn` content
enters only through the integrability of the reparametrised integrand (`prod_integrable_on`). -/
theorem tangential_halfspace_reparam_iterated_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w)
    (k : Fin (n + 1)) (hk : k ≠ 0) :
    ∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
        lineDeriv ℝ (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
          y (EuclideanSpace.single k 1) ∂MeasureTheory.volume
      = ∫ t in {t : EuclideanSpace ℝ (Fin n) |
            0 ≤ (LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
                  (faceEmbedL t)) 0},
          (∫ x : ℝ,
            lineDeriv ℝ (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
              (x • EuclideanSpace.single k 1 +
                LinearIsometryEquiv.piLpCongrLeft 2 ℝ ℝ (Equiv.swap (0 : Fin (n + 1)) k)
                  (faceEmbedL t))
              (EuclideanSpace.single k 1) ∂MeasureTheory.volume)
          ∂MeasureTheory.volume := by
  have h1 := reparam_to_prod_generic
      (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) k hk
  have h_integ := prod_integrable_on w hw hwsupp k hk
  have h2 := prod_fubini_to_iterated_generic
      (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) k hk h_integ
  exact h1.trans h2

/-- The half-space integral of `lineDeriv ℝ (w · tuple) y (single k 1)` vanishes for `k ≠ 0`,
when `w` is `ContDiffOn ℝ ∞` on `range 𝓡∂` and has compact support.
This combines the swap-reparametrisation/Fubini identity with the vanishing of each
constrained slice integral. -/
theorem halfspace_tangential_linederiv_integral_zero_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w)
    (k : Fin (n + 1)) (hk : k ≠ 0) :
    ∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
        lineDeriv ℝ (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
          y (EuclideanSpace.single k 1) ∂MeasureTheory.volume = 0 := by
  have h_iter := tangential_halfspace_reparam_iterated_on w hw hwsupp k hk
  have h_slice := tangential_reparam_outer_integral_zero_on w hw hwsupp k hk
  rw [h_iter]
  exact h_slice

/-- The half-space integral of `(-1)^k • fderivWithin ℝ (w · tuple) (range 𝓡∂) y (basisFun k)`
equals `(-1)^k` times the half-space integral of `lineDeriv ℝ (w · tuple) y (single k 1)`,
for `k ≠ 0`. The scalar `(-1)^k` pulls out of the integral via `integral_smul`, and then
`setIntegral_congr_fun` reduces to the pointwise identity `tangential_fderivwithin_eq_linederiv`. -/
theorem tangential_fderivwithin_integral_eq_linederiv {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w)
    (k : Fin (n + 1)) (hk : k ≠ 0) :
    ∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
        ((-1 : ℝ)) ^ (k : ℕ) •
          fderivWithin ℝ
            (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
            (Set.range (𝓡∂ (n + 1))) y
            (EuclideanSpace.basisFun (Fin (n + 1)) ℝ k) ∂MeasureTheory.volume
      = ((-1 : ℝ)) ^ (k : ℕ) •
        ∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
          lineDeriv ℝ (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
            y (EuclideanSpace.single k 1) ∂MeasureTheory.volume := by
  rw [integral_smul]
  congr 1
  refine setIntegral_congr_fun ?_ (fun y hy ↦ ?_)
  · exact measurableSet_le measurable_const
      ((measurable_pi_apply 0).comp (WithLp.measurable_ofLp 2 _))
  · exact tangential_fderivwithin_eq_linederiv w hw k hk y hy

/-- The half-space integral of `(-1)^k • fderivWithin ℝ (w · tuple) (range 𝓡∂) y (basisFun k)`
vanishes for `k ≠ 0`, when `w` is `ContDiffOn ℝ ∞` on `range 𝓡∂` and has compact support.
Follows by combining `tangential_fderivwithin_integral_eq_linederiv` with
`halfspace_tangential_linederiv_integral_zero_on` and `smul_zero`. -/
theorem halfspace_tangential_fderivwithin_integral_zero_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w)
    (k : Fin (n + 1)) (hk : k ≠ 0) :
    ∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
        ((-1 : ℝ)) ^ (k : ℕ) •
          fderivWithin ℝ
            (fun z ↦ w z (k.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
            (Set.range (𝓡∂ (n + 1))) y
            (EuclideanSpace.basisFun (Fin (n + 1)) ℝ k) ∂MeasureTheory.volume = 0 := by
  have hA := tangential_fderivwithin_integral_eq_linederiv w hw hwsupp k hk
  have hB := halfspace_tangential_linederiv_integral_zero_on w hw hwsupp k hk
  rw [hA, hB, smul_zero]

/-- Half-space FTC for the divergence sum (ContDiffOn-on-half-space version):
the integral of `∑ᵢ (-1)^i • fderivWithin ℝ (w · (i.removeNth basisFun)) (range 𝓡∂) y (basisFun i)`
over `{y | 0 ≤ y 0}` equals `-∫ w (faceEmbedL t) (Fin.removeNth 0 basisFun) dt`.
After swapping the integral with the finite sum, `Finset.sum_eq_single 0` collapses the sum
to the normal (`i = 0`) FTC term (via `halfspace_normal_fderivWithin_integral_eq_neg_face_on`)
while every tangential (`i ≠ 0`) term vanishes (via
`halfspace_tangential_fderivwithin_integral_zero_on`). -/
theorem halfspace_div_fderivwithin_eq_neg_face_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w) :
    ∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
        (∑ i : Fin (n + 1),
            ((-1 : ℝ)) ^ (i : ℕ) •
              fderivWithin ℝ
                (fun z ↦ w z (i.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
                (Set.range (𝓡∂ (n + 1))) y
                (EuclideanSpace.basisFun (Fin (n + 1)) ℝ i)) ∂MeasureTheory.volume
      = - ∫ t : EuclideanSpace ℝ (Fin n),
          w (faceEmbedL t)
            (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)) ∂MeasureTheory.volume := by
  have h_swap := halfspace_div_fderivWithin_finsetSum_swap_on w hw hwsupp
  rw [h_swap, Finset.sum_eq_single (0 : Fin (n + 1))]
  · exact halfspace_normal_fderivWithin_integral_eq_neg_face_on w hw hwsupp
  · intro k _ hk
    exact halfspace_tangential_fderivwithin_integral_zero_on w hw hwsupp k hk
  · intro h; exact absurd (Finset.mem_univ 0) h

/-- Half-space FTC for the exterior derivative top coefficient (ContDiffOn-on-half-space version):
the integral of `topCoeff (extDerivWithin w (range 𝓡∂) y)` over `{y | 0 ≤ y 0}` equals
`-∫ w (faceEmbedL t) (Fin.removeNth 0 basisFun) dt`.
The LHS integrand is expanded pointwise via `topcoeff_extderiv_expand_on` and
`setIntegral_congr_fun`, then `halfspace_div_fderivwithin_eq_neg_face_on` closes the
resulting divergence integral. -/
theorem halfspace_topcoeff_extderiv_eq_neg_face_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w) :
    ∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
        topCoeff (extDerivWithin w (Set.range (𝓡∂ (n + 1))) y) ∂MeasureTheory.volume
      = - ∫ t : EuclideanSpace ℝ (Fin n),
          w (faceEmbedL t)
            (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)) ∂MeasureTheory.volume := by
  have h_meas : MeasurableSet {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0} :=
    measurableSet_le measurable_const ((measurable_pi_apply 0).comp (WithLp.measurable_ofLp 2 _))
  have h_expand := topcoeff_extderiv_expand_on w hw
  have h_div := halfspace_div_fderivwithin_eq_neg_face_on w hw hwsupp
  exact (setIntegral_congr_fun h_meas h_expand).trans h_div

end Library.Geometry.Manifold.HalfspaceTangentialFTC
