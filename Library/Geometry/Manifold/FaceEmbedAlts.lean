import Library.Geometry.Manifold.DiffFormBundle        -- DiffForm
import Library.Geometry.Manifold.InducedOrientDefs       -- inducedOrientFun (P12)
import Library.Geometry.Manifold.InducedOrientSmooth      -- contMDiff_inducedOrientFun (P12)
import Library.Geometry.Manifold.StokesIntegralDefs      -- OrientedManifold (+ refForm)
import Library.Geometry.ManifoldBdry.BdryIsManifold       -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBoundary.CompactBdry      -- Bdry
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.Normed.Module.Alternating.Basic
import Mathlib.Analysis.Normed.Module.Alternating.Curry
import Mathlib.Data.Fin.VecNotation
import Mathlib.LinearAlgebra.Alternating.Basic
import Mathlib.LinearAlgebra.Dimension.Constructions
import Mathlib.LinearAlgebra.Dimension.OrzechProperty
import Mathlib.LinearAlgebra.FiniteDimensional.Basic
import Mathlib.LinearAlgebra.Orientation
import Mathlib.Topology.Algebra.Module.Alternating.Basic
import Mathlib.Topology.Algebra.Module.Alternating.Topology

/-!
# Face embedding and alternating forms

Algebraic lemmas relating the face embedding `faceEmbedL : ℝⁿ →L[ℝ] ℝⁿ⁺¹` to
top-degree alternating forms.  These are the key pointwise identities used in the
proof of the Stokes boundary orientation formula.

## Main statements

- `alt_cons_smul_sub`: multilinearity of an alternating form in the first slot via
  `map_vecCons_sub` and `vecCons_smul`.
- `alt_face_range_zero`: an alternating form vanishes on vectors in the image of
  `faceEmbedL`, since they are linearly dependent.
- `face_normal_comp_family`: slot-wise description of a family composed with `faceEmbedL`.
- `alt_normal_eval_smul`: scalar-factoring of an alternating form evaluation through
  `faceEmbedL`.
- `face_embed_basis`: `faceEmbedL` sends the `i`-th basis vector to `e_{i.succ}`.
- `curry_face_apply_basis`: explicit evaluation of the curried face form on the basis.
- `top_form_basis_ne_zero`: a nonzero top form evaluates to a nonzero scalar on the basis.
- `curry_face_ne_zero`: the curried face form is nonzero whenever `f` is nonzero.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.InducedOrientDefs
open Library.Geometry.Manifold.InducedOrientSmooth
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBoundary.CompactBdry
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.FaceEmbedAlts

variable {n : ℕ}

/-- Multilinearity of an alternating form in slot 0: `φ(a·x − y, g) = a·φ(x, g) − φ(y, g)`.
This follows from `map_vecCons_sub` and `vecCons_smul`. -/
theorem alt_cons_smul_sub
    (φ : EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin (n + 1)]→L[ℝ] ℝ)
    (a : ℝ) (x y : EuclideanSpace ℝ (Fin (n + 1)))
    (g : Fin n → EuclideanSpace ℝ (Fin (n + 1))) :
    φ (Matrix.vecCons (a • x - y) g)
      = a • φ (Matrix.vecCons x g) - φ (Matrix.vecCons y g) := by
  rw [φ.map_vecCons_sub, φ.vecCons_smul]

/-- An alternating `(n+1)`-form vanishes when all `n+1` argument vectors lie in the image of
`faceEmbedL : ℝⁿ →L[ℝ] ℝⁿ⁺¹`, since they are linearly dependent (rank at most `n`). -/
theorem alt_face_range_zero
    (φ : EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin (n + 1)]→L[ℝ] ℝ)
    (t : EuclideanSpace ℝ (Fin n))
    (w : Fin n → EuclideanSpace ℝ (Fin n)) :
    φ (Matrix.vecCons (faceEmbedL t) (⇑faceEmbedL ∘ w)) = 0 := by
  have h_mem : ∀ i, Matrix.vecCons (faceEmbedL t) (⇑faceEmbedL ∘ w) i ∈
      LinearMap.range (faceEmbedL (n := n)).toLinearMap := by
    intro i
    refine Fin.cases ?_ ?_ i
    · exact ⟨t, rfl⟩
    · intro j; exact ⟨w j, rfl⟩
  have h_dep : ¬ LinearIndependent ℝ (Matrix.vecCons (faceEmbedL t) (⇑faceEmbedL ∘ w)) := by
    intro h
    have hcard := linearIndependent_iff_card_le_finrank_span.mp h
    have hle : Submodule.span ℝ
        (Set.range (Matrix.vecCons (faceEmbedL t) (⇑faceEmbedL ∘ w))) ≤
        LinearMap.range (faceEmbedL (n := n)).toLinearMap :=
      Submodule.span_le.mpr (Set.range_subset_iff.mpr h_mem)
    have h1 := Submodule.finrank_mono hle
    have h2 : Module.finrank ℝ (LinearMap.range (faceEmbedL (n := n)).toLinearMap) ≤ n :=
      (LinearMap.finrank_range_le _).trans_eq finrank_euclideanSpace_fin
    rw [Fintype.card_fin] at hcard
    exact absurd (hcard.trans (h1.trans h2)) (by omega)
  exact φ.toAlternatingMap.map_linearDependent _ h_dep

/-- Given $A \circ \text{faceEmbedL} = \text{faceEmbedL} \circ B'$ and $B'(B(v)) = v$ for all
$v$, and $A(e_0) = a \cdot e_0 + \text{faceEmbedL}(t)$, composing $A$ with the family
$[-e_0,\ \text{faceEmbedL} \circ B \circ w]$ yields $[a \cdot (-e_0) - \text{faceEmbedL}(t),\
\text{faceEmbedL} \circ w]$ pointwise. -/
theorem face_normal_comp_family
    (A : EuclideanSpace ℝ (Fin (n + 1)) →L[ℝ] EuclideanSpace ℝ (Fin (n + 1)))
    (B B' : EuclideanSpace ℝ (Fin n) →L[ℝ] EuclideanSpace ℝ (Fin n))
    (a : ℝ) (t : EuclideanSpace ℝ (Fin n))
    (hA : A.comp faceEmbedL = faceEmbedL.comp B')
    (hBB : ∀ v : EuclideanSpace ℝ (Fin n), B' (B v) = v)
    (hAe : A (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)
      = a • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)
    (w : Fin n → EuclideanSpace ℝ (Fin n)) :
    ⇑A ∘ Matrix.vecCons (-(EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0))
        (⇑faceEmbedL ∘ ⇑B ∘ w)
      = Matrix.vecCons
          (a • -(EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0) - faceEmbedL t)
          (⇑faceEmbedL ∘ w) := by
  funext i
  refine Fin.cases ?_ (fun j ↦ ?_) i
  · simp only [Function.comp, Matrix.cons_val_zero]
    rw [map_neg, hAe]
    simp only [smul_neg]; abel
  · simp only [Function.comp, Matrix.cons_val_succ]
    have hAx := DFunLike.congr_fun hA (B (w j))
    simp only [ContinuousLinearMap.comp_apply] at hAx
    rw [hAx, hBB]

/-- Evaluating an alternating form on the face-normal composed family factors out the scalar `a`:
the `faceEmbedL`-defect term vanishes by `alt_face_range_zero`. -/
theorem alt_normal_eval_smul
    (φ : EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin (n + 1)]→L[ℝ] ℝ)
    (A : EuclideanSpace ℝ (Fin (n + 1)) →L[ℝ] EuclideanSpace ℝ (Fin (n + 1)))
    (B B' : EuclideanSpace ℝ (Fin n) →L[ℝ] EuclideanSpace ℝ (Fin n))
    (a : ℝ) (t : EuclideanSpace ℝ (Fin n))
    (hA : A.comp faceEmbedL = faceEmbedL.comp B')
    (hBB : ∀ v : EuclideanSpace ℝ (Fin n), B' (B v) = v)
    (hAe : A (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)
      = a • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)
    (w : Fin n → EuclideanSpace ℝ (Fin n)) :
    φ (⇑A ∘ Matrix.vecCons (-(EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0))
        (⇑faceEmbedL ∘ ⇑B ∘ w))
      = a • φ (Matrix.vecCons (-(EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0))
          (⇑faceEmbedL ∘ w)) := by
  have h_comp := face_normal_comp_family A B B' a t hA hBB hAe w
  have h_lin := alt_cons_smul_sub φ a
    (-(EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)) (faceEmbedL t) (⇑faceEmbedL ∘ w)
  have h_zero := alt_face_range_zero φ t w
  rw [h_comp, h_lin, h_zero, sub_zero]

/-- `faceEmbedL` maps the `i`-th standard basis vector of `ℝⁿ` to the `i.succ`-th basis vector
of `ℝⁿ⁺¹`. -/
theorem face_embed_basis (i : Fin n) :
    faceEmbedL (EuclideanSpace.basisFun (Fin n) ℝ i)
      = EuclideanSpace.basisFun (Fin (n + 1)) ℝ i.succ := by
  ext j
  simp only [faceEmbedL, ContinuousLinearMap.sum_apply, ContinuousLinearMap.smulRight_apply,
    EuclideanSpace.basisFun_apply, EuclideanSpace.single]
  simp only [EuclideanSpace.proj, PiLp.proj, ContinuousLinearMap.coe_mk',
    PiLp.ofLp_single, Pi.single_apply]
  simp only [PiLp.projₗ_apply, PiLp.single_apply]
  simp only [ite_smul, one_smul, zero_smul, Finset.sum_ite_eq', Finset.mem_univ, if_true]
  simp only [PiLp.ofLp_single, Pi.single_apply]

/-- The curried face form evaluated on the boundary basis equals `−f(e₀, e₁, …, eₙ)`.
Uses linearity of `curryLeft` to pull out the sign, then rewrites slots via `face_embed_basis`. -/
theorem curry_face_apply_basis
    (f : EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin (n + 1)]→L[ℝ] ℝ) :
    (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
      (f.curryLeft (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)))
      (fun i ↦ EuclideanSpace.basisFun (Fin n) ℝ i)
      = -(f (fun j ↦ EuclideanSpace.basisFun (Fin (n + 1)) ℝ j)) := by
  have h_neg : f.curryLeft (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)
      = -(f.curryLeft (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)) := map_neg _ _
  rw [h_neg, map_neg, ContinuousAlternatingMap.neg_apply, neg_inj,
    ContinuousAlternatingMap.compContinuousLinearMapCLM_apply,
    ContinuousAlternatingMap.compContinuousLinearMap_apply,
    ContinuousAlternatingMap.curryLeft_apply_apply]
  congr 1
  funext j
  refine Fin.cases ?_ (fun i ↦ ?_) j
  · simp
  · simpa using face_embed_basis i

/-- A nonzero top-degree continuous alternating form evaluates to a nonzero scalar on the
ordered standard basis, by `AlternatingMap.map_basis_ne_zero_iff`. -/
theorem top_form_basis_ne_zero
    (f : EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin (n + 1)]→L[ℝ] ℝ) (hf : f ≠ 0) :
    f (fun j ↦ EuclideanSpace.basisFun (Fin (n + 1)) ℝ j) ≠ 0 :=
  (AlternatingMap.map_basis_ne_zero_iff
    ((EuclideanSpace.basisFun (Fin (n + 1)) ℝ).toBasis) f.toAlternatingMap).mpr
    (fun h ↦ hf (ContinuousAlternatingMap.toAlternatingMap_injective h))

/-- If `f ≠ 0`, the curried face form `faceEmbedL*(f.curryLeft(−e₀))` is also nonzero:
if it were zero, evaluating on the boundary basis would force `f(basis) = 0`, contradicting
`top_form_basis_ne_zero`. -/
theorem curry_face_ne_zero
    (f : EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin (n + 1)]→L[ℝ] ℝ) (hf : f ≠ 0) :
    ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
      (f.curryLeft (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)) ≠ 0 := by
  intro h0
  have h_basis : f (fun j ↦ EuclideanSpace.basisFun (Fin (n + 1)) ℝ j) ≠ 0 :=
    top_form_basis_ne_zero f hf
  have h_eval : (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
      (f.curryLeft (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)))
      (fun i ↦ EuclideanSpace.basisFun (Fin n) ℝ i)
      = -(f (fun j ↦ EuclideanSpace.basisFun (Fin (n + 1)) ℝ j)) :=
    curry_face_apply_basis f
  rw [h0] at h_eval
  simp only [ContinuousAlternatingMap.coe_zero, Pi.zero_apply] at h_eval
  exact h_basis (neg_eq_zero.mp h_eval.symm)

end Library.Geometry.Manifold.FaceEmbedAlts
