import Mathlib.Algebra.DirectSum.Module
import Mathlib.Algebra.Polynomial.Module.AEval
import Mathlib.Data.Matrix.Block
import Mathlib.LinearAlgebra.BilinearMap
import Mathlib.LinearAlgebra.DirectSum.Basis
import Mathlib.LinearAlgebra.FiniteDimensional.Defs
import Mathlib.LinearAlgebra.Matrix.Basis
import Mathlib.RingTheory.AdjoinRoot
import Mathlib.Tactic.NoncommRing

/-!
# Direct-Sum Decomposition for the Rational Canonical Form

This file establishes the block-diagonal matrix representation of multiplication by `X` on a
direct sum `⨁ᵢ K[X]/(fᵢ)` of cyclic `K[X]`-modules.  The key step is showing that the
`DFinsupp.basis` built from the individual power bases interacts with the `X`-action in a
block-diagonal fashion, one block per factor.

## Main statements

- `dfinsupp_basis_repr_component`: component formula for `DFinsupp.basis.repr`.
- `dfinsupp_basis_diag_component`: diagonal component of a `DFinsupp.basis` vector.
- `dfinsupp_basis_offdiag_component_zero`: off-diagonal component is zero.
- `lsmul_x_offdiag_component_zero`: the `i'`-th component of `X • eⱼₗ` is zero for `i' ≠ j`.
- `lsmul_x_offdiag_repr_zero`: `repr` of that zero component is zero.
- `lsmul_x_diag_component`: diagonal component of `X • eⱼₗ`.
- `conj_matrix`: matrix of `T` in a conjugated basis equals matrix of `S` in the target basis.
- `intertwine_x`: the isomorphism to the direct sum intertwines `T` with `X`-multiplication.
- `block_diag`: the matrix of `X`-multiplication is block-diagonal in the `DFinsupp.basis`.
-/

namespace Library.LinearAlgebra.RationalCanonicalForm.DirectSumDecomp

variable {K : Type*} [Field K]

/-- The matrix of `T` in the basis `c.map g.symm` equals the matrix of `S` in `c`,
provided `g` intertwines `T` and `S`. -/
theorem conj_matrix {ι : Type*} [Fintype ι] [DecidableEq ι]
    {V : Type*} [AddCommGroup V] [Module K V]
    {W : Type*} [AddCommGroup W] [Module K W]
    (g : V ≃ₗ[K] W) (c : Module.Basis ι K W) (T : V →ₗ[K] V) (S : W →ₗ[K] W)
    (h : ∀ v : V, g (T v) = S (g v)) :
    LinearMap.toMatrix (c.map g.symm) (c.map g.symm) T = LinearMap.toMatrix c c S := by
  ext i j
  simp only [LinearMap.toMatrix_apply]
  change (c.repr (g (T (g.symm (c j))))) i = (c.repr (S (c j))) i
  rw [h, g.apply_symm_apply]

/-- The isomorphism `e : Module.AEval' T ≃ₗ[K[X]] ⨁ᵢ K[X]/(fᵢ)` intertwines `T` with
multiplication by `X` on the direct sum. -/
theorem intertwine_x
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V) {r : ℕ} (f : Fin r → Polynomial K)
    (e : Module.AEval' T ≃ₗ[Polynomial K]
        DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
    (v : V) :
    ((Module.AEval'.of T).trans (e.restrictScalars K)) (T v)
      = ((LinearMap.lsmul (Polynomial K)
            (DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
            Polynomial.X).restrictScalars K)
          (((Module.AEval'.of T).trans (e.restrictScalars K)) v) := by
  simp only [LinearEquiv.trans_apply, LinearMap.lsmul_apply, LinearMap.restrictScalars_apply]
  rw [← Module.AEval'.X_smul_of]
  exact e.map_smul Polynomial.X _

section DirectSumComponents

variable {r : ℕ} (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic)

/-- The `repr` of an element `g` in the `DFinsupp.basis` at index `⟨i', k'⟩` equals
the `repr` of the `i'`-th component of `g` at `k'` in the power basis of `K[X]/(f i')`. -/
theorem dfinsupp_basis_repr_component
    (g : DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
    (i' : Fin r) (k' : Fin (AdjoinRoot.powerBasis' (hmonic i')).dim) :
    (DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis)).repr g ⟨i', k'⟩
      = (AdjoinRoot.powerBasis' (hmonic i')).basis.repr (g i') k' := by noncomm_ring

/-- The `j`-th component of the `⟨j, l⟩`-th basis vector of the `DFinsupp.basis` is the
`l`-th power basis element of `K[X]/(f j)`. -/
theorem dfinsupp_basis_diag_component
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim) :
    (DFinsupp.basis fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis) ⟨j, l⟩ j
      = (AdjoinRoot.powerBasis' (hmonic j)).basis l := by
  change ((DFinsupp.basis fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis).repr.symm
      (Finsupp.single ⟨j, l⟩ 1)) j = _
  simp only [DFinsupp.basis, LinearEquiv.symm_trans_apply,
    DFinsupp.mapRange.linearEquiv_symm, LinearEquiv.symm_symm,
    DFinsupp.mapRange.linearEquiv_apply, DFinsupp.mapRange_apply,
    sigmaFinsuppLequivDFinsupp_apply, AddEquiv.toFun_eq_coe,
    sigmaFinsuppAddEquivDFinsupp_apply,
    sigmaFinsuppEquivDFinsupp_single, DFinsupp.single_eq_same]
  exact rfl

/-- For `i' ≠ j`, the `i'`-th component of the `⟨j, l⟩`-th `DFinsupp.basis` vector is zero. -/
theorem dfinsupp_basis_offdiag_component_zero
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim)
    (i' : Fin r) (h : i' ≠ j) :
    ((DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) i' = 0 := by
  apply (AdjoinRoot.powerBasis' (hmonic i')).basis.repr.injective
  ext k'
  simp only [map_zero, Finsupp.coe_zero, Pi.zero_apply]
  have repr_formula :
      (AdjoinRoot.powerBasis' (hmonic i')).basis.repr
        (((DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) i') k' =
      (DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis)).repr
        ((DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) ⟨i', k'⟩ :=
    rfl
  rw [repr_formula]
  have hrepr_self :
      (DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis)).repr
        ((DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) =
      Finsupp.single ⟨j, l⟩ 1 := LinearEquiv.apply_symm_apply _ _
  rw [hrepr_self]
  exact Finsupp.single_eq_of_ne (fun heq ↦ h (Sigma.mk.inj heq).1)

/-- For `i' ≠ j`, the `i'`-th component of `X • eⱼₗ` in the direct sum is zero,
since each summand `K[X]/(fᵢ)` is invariant under `X`-multiplication. -/
theorem lsmul_x_offdiag_component_zero
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim)
    (i' : Fin r) (h : i' ≠ j) :
    (((LinearMap.lsmul (Polynomial K)
        (DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
        Polynomial.X).restrictScalars K)
      ((DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩)) i' = 0 := by
  rw [LinearMap.restrictScalars_apply, LinearMap.lsmul_apply,
    DirectSum.smul_apply (M := fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i})]
  have hcomp := dfinsupp_basis_offdiag_component_zero f hmonic j l i' h
  convert smul_zero Polynomial.X using 2

/-- The `k'`-th coordinate of `repr` of the `i'`-th component of `X • eⱼₗ` is zero
when `i' ≠ j`. -/
theorem lsmul_x_offdiag_repr_zero
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim)
    (i' : Fin r) (k' : Fin (AdjoinRoot.powerBasis' (hmonic i')).dim) (h : i' ≠ j) :
    (AdjoinRoot.powerBasis' (hmonic i')).basis.repr
      (((LinearMap.lsmul (Polynomial K)
          (DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
          Polynomial.X).restrictScalars K)
        ((DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) i') k' =
        0 := by
  have hcomp :
      (((LinearMap.lsmul (Polynomial K)
          (DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
          Polynomial.X).restrictScalars K)
        ((DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩)) i' = 0 :=
    lsmul_x_offdiag_component_zero f hmonic j l i' h
  rw [hcomp]
  exact congrFun (congrArg _ (map_zero _)) k'

/-- The `j`-th component of `X • eⱼₗ` in the direct sum equals `root(fⱼ)` times the
`l`-th power basis element, reflecting the `K[X]`-module structure of `K[X]/(fⱼ)`. -/
theorem lsmul_x_diag_component (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim) :
    ((LinearMap.lsmul (Polynomial K)
        (DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
        Polynomial.X).restrictScalars K)
      ((DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) j
      = AdjoinRoot.root (f j) * (AdjoinRoot.powerBasis' (hmonic j)).basis l := by
  rw [LinearMap.restrictScalars_apply, LinearMap.lsmul_apply]
  rw [DirectSum.smul_apply (M := fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i})
      Polynomial.X _ j]
  have hcomp : (DFinsupp.basis fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis) ⟨j, l⟩ j
      = (AdjoinRoot.powerBasis' (hmonic j)).basis l :=
    dfinsupp_basis_diag_component f hmonic j l
  change AdjoinRoot.root (f j) *
      ((DFinsupp.basis fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis) ⟨j, l⟩ j)
      = AdjoinRoot.root (f j) * (AdjoinRoot.powerBasis' (hmonic j)).basis l
  exact congrArg (fun w ↦ AdjoinRoot.root (f j) * w) hcomp

/-- **Block-diagonal X-multiplication**: in the `DFinsupp.basis` built from the individual
power bases, the matrix of multiplication by `X` on `⨁ᵢ K[X]/(fᵢ)` is block-diagonal,
with the `i`-th block equal to the matrix of multiplication by `root(fᵢ)` in the power
basis of `K[X]/(fᵢ)`. -/
theorem block_diag :
    LinearMap.toMatrix
        (DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis))
        (DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis))
        ((LinearMap.lsmul (Polynomial K)
            (DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
            Polynomial.X).restrictScalars K)
      = Matrix.blockDiagonal' (fun i ↦
          LinearMap.toMatrix (AdjoinRoot.powerBasis' (hmonic i)).basis
            (AdjoinRoot.powerBasis' (hmonic i)).basis
            (LinearMap.mulLeft K (AdjoinRoot.root (f i)))) := by
  ext ⟨i, k⟩ ⟨j, l⟩
  rw [LinearMap.toMatrix_apply]
  have hB := dfinsupp_basis_repr_component f hmonic
  rw [hB]
  have hdiag := lsmul_x_diag_component f hmonic
  have hoff := lsmul_x_offdiag_repr_zero f hmonic
  by_cases h : i = j
  · subst h
    rw [Matrix.blockDiagonal'_apply_eq, LinearMap.toMatrix_apply, LinearMap.mulLeft_apply]
    exact congrArg (fun w ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis.repr w k) (hdiag i l)
  · rw [Matrix.blockDiagonal'_apply_ne
      (fun i ↦ LinearMap.toMatrix (AdjoinRoot.powerBasis' (hmonic i)).basis
        (AdjoinRoot.powerBasis' (hmonic i)).basis
        (LinearMap.mulLeft K (AdjoinRoot.root (f i)))) k l h]
    exact hoff j l i k h

end DirectSumComponents

end Library.LinearAlgebra.RationalCanonicalForm.DirectSumDecomp
