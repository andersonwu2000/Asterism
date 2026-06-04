import Mathlib

namespace Library.LinearAlgebra.RationalCanonicalForm.DirectSumDecomp

-- entry_kind: Builder
theorem dfinsupp_basis_repr_component {K : Type*} [Field K] {r : ℕ}
    (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic)
    (g : DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
    (i' : Fin r) (k' : Fin (AdjoinRoot.powerBasis' (hmonic i')).dim) :
    (DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)).repr g ⟨i', k'⟩
      = (AdjoinRoot.powerBasis' (hmonic i')).basis.repr (g i') k' := by noncomm_ring

-- dfinsupp_basis_diag_component: j-th component of DFinsupp.basis ⟨j,l⟩ equals the j-th basis
-- vector (pb j) l; proved by unfolding Basis.ofRepr repr via symm_trans_apply + mapRange_single
-- + sigmaFinsuppEquivDFinsupp_single + DFinsupp.single_eq_same chain.
-- entry_kind: Builder
theorem dfinsupp_basis_diag_component {K : Type*} [Field K] {r : ℕ}
    (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic)
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim) :
    (DFinsupp.basis fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis) ⟨j, l⟩ j
      = (AdjoinRoot.powerBasis' (hmonic j)).basis l := by
  change ((DFinsupp.basis fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis).repr.symm
      (Finsupp.single ⟨j, l⟩ 1)) j = _
  simp only [DFinsupp.basis, LinearEquiv.symm_trans_apply,
    DFinsupp.mapRange.linearEquiv_symm, LinearEquiv.symm_symm,
    DFinsupp.mapRange.linearEquiv_apply, DFinsupp.mapRange_apply,
    sigmaFinsuppLequivDFinsupp_apply, AddEquiv.toFun_eq_coe,
    sigmaFinsuppAddEquivDFinsupp_apply,
    sigmaFinsuppEquivDFinsupp_single, DFinsupp.single_eq_same]
  exact rfl

-- dfinsupp_basis_offdiag_component_zero: off-diagonal component of a DFinsupp.basis vector
-- is zero; proved via repr injectivity + LinearEquiv.apply_symm_apply + Finsupp.single_eq_of_ne.
-- entry_kind: Builder
theorem dfinsupp_basis_offdiag_component_zero {K : Type*} [Field K] {r : ℕ}
    (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic)
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim)
    (i' : Fin r) (h : i' ≠ j) :
    ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) i' = 0 := by
  apply (AdjoinRoot.powerBasis' (hmonic i')).basis.repr.injective
  ext k'
  simp only [map_zero, Finsupp.coe_zero, Pi.zero_apply]
  have repr_formula : (AdjoinRoot.powerBasis' (hmonic i')).basis.repr
      (((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) i') k' =
      (DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)).repr
        ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) ⟨i', k'⟩ :=
    rfl
  rw [repr_formula]
  have hrepr_self : (DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)).repr
      ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) =
      Finsupp.single ⟨j, l⟩ 1 := LinearEquiv.apply_symm_apply _ _
  rw [hrepr_self]
  exact Finsupp.single_eq_of_ne (fun heq => h (Sigma.mk.inj heq).1)

-- Off-diagonal component vanishes: the X-action on the direct sum is component-wise,
-- so the i'-th component of `X • eⱼₗ` is `X • (eⱼₗ i')`. The basis vector `eⱼₗ` is
-- supported only on summand `j`, hence its i'-th component (i' ≠ j) is `0`
-- (sub-goal `dfinsupp_basis_offdiag_component_zero`, a pure basis-support fact stripped
-- of the lsmul/restrictScalars layers); `convert smul_zero` then collapses `X • 0`.
theorem lsmul_x_offdiag_component_zero {K : Type*} [Field K] {r : ℕ}
    (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic)
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim)
    (i' : Fin r) (h : i' ≠ j) :
    (((LinearMap.lsmul (Polynomial K)
        (DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
        Polynomial.X).restrictScalars K)
      ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩)) i' = 0  := by
  rw [LinearMap.restrictScalars_apply, LinearMap.lsmul_apply,
    DirectSum.smul_apply (M := fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i})]
  have hcomp := dfinsupp_basis_offdiag_component_zero f hmonic j l i' h
  convert smul_zero Polynomial.X using 2

-- Off-diagonal repr-zero: reduce to the single component fact that the `i'`-th
-- summand of `X • eⱼₗ` vanishes (`lsmul_x_offdiag_component_zero`), since `i' ≠ j`
-- and the X-action is component-wise; the parent's `repr ... k'` layer then collapses
-- via `map_zero`. The sub-goal drops the outer `repr`/`k'` coordinate — strictly simpler.
theorem lsmul_x_offdiag_repr_zero {K : Type*} [Field K] {r : ℕ}
    (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic)
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim)
    (i' : Fin r) (k' : Fin (AdjoinRoot.powerBasis' (hmonic i')).dim) (h : i' ≠ j) :
    (AdjoinRoot.powerBasis' (hmonic i')).basis.repr
      (((LinearMap.lsmul (Polynomial K)
          (DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
          Polynomial.X).restrictScalars K)
        ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) i') k' = 0  := by
  -- The X-action on `⨁ᵢ K[X]/(fᵢ)` is component-wise and each summand is invariant,
  -- so the `i'`-th component of `X • eⱼₗ` (with `i' ≠ j`) is the zero element of the
  -- `i'`-th fiber; the `repr` of `0` at any coordinate is `0`.
  have hcomp :
      (((LinearMap.lsmul (Polynomial K)
          (DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
          Polynomial.X).restrictScalars K)
        ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩)) i' = 0 :=
    lsmul_x_offdiag_component_zero f hmonic j l i' h
  rw [hcomp]
  exact congrFun (congrArg _ (map_zero _)) k'

-- Diagonal component of the `X`-action: peel the `lsmul`/`restrictScalars`/`DirectSum.smul`
-- wrappers (`restrictScalars_apply`, `lsmul_apply`, `DirectSum.smul_apply` pinned to the
-- `Submodule.span` fiber family), reducing the goal to `X • eⱼₗ-component = root fⱼ * basis l`.
-- The `X`-smul (on `K[X] ⧸ Submodule.span {fⱼ}`) is defeq to `root fⱼ * ·` (the `AdjoinRoot`
-- multiplication), so `change` rephrases the LHS as `root fⱼ * component` and `congrArg`
-- transports the single remaining fact:
--   `dfinsupp_basis_diag_component` — the `j`-th component of `DFinsupp.basis pb ⟨j,l⟩` is
--   `pb j l`. That sub-goal is a pure `DFinsupp.basis` evaluation (no `X`-action, no quotient
--   seam) — strictly simpler than the parent. The `X•·`/`root*·` instance bridge stays inline
--   here (it is unstatable as a standalone single-variable lemma).
theorem lsmul_x_diag_component {K : Type*} [Field K] {r : ℕ}
    (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic)
    (j : Fin r) (l : Fin (AdjoinRoot.powerBasis' (hmonic j)).dim) :
    ((LinearMap.lsmul (Polynomial K)
        (DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
        Polynomial.X).restrictScalars K)
      ((DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis)) ⟨j, l⟩) j
      = AdjoinRoot.root (f j) * (AdjoinRoot.powerBasis' (hmonic j)).basis l  := by
  rw [LinearMap.restrictScalars_apply, LinearMap.lsmul_apply]
  rw [DirectSum.smul_apply (M := fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i})
      Polynomial.X _ j]
  have hcomp : (DFinsupp.basis fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis) ⟨j, l⟩ j
      = (AdjoinRoot.powerBasis' (hmonic j)).basis l :=
    dfinsupp_basis_diag_component f hmonic j l
  change AdjoinRoot.root (f j) *
      ((DFinsupp.basis fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis) ⟨j, l⟩ j)
      = AdjoinRoot.root (f j) * (AdjoinRoot.powerBasis' (hmonic j)).basis l
  exact congrArg (fun w => AdjoinRoot.root (f j) * w) hcomp

-- entry_kind: Builder
-- conj_matrix: conjugation lemma — toMatrix in pulled-back basis equals toMatrix in original
-- basis, using `change` to exploit definitional equalities of Basis.map + intertwining h.
theorem conj_matrix {K : Type*} [Field K] {ι : Type*} [Fintype ι] [DecidableEq ι]
    {V : Type*} [AddCommGroup V] [Module K V]
    {W : Type*} [AddCommGroup W] [Module K W]
    (g : V ≃ₗ[K] W) (c : Module.Basis ι K W) (T : V →ₗ[K] V) (S : W →ₗ[K] W)
    (h : ∀ v : V, g (T v) = S (g v)) :
    LinearMap.toMatrix (c.map g.symm) (c.map g.symm) T = LinearMap.toMatrix c c S := by
  ext i j
  simp only [LinearMap.toMatrix_apply]
  change (c.repr (g (T (g.symm (c j))))) i = (c.repr (S (c j))) i
  rw [h, g.apply_symm_apply]

-- entry_kind: Builder
-- intertwine_x: AEval'.of T composed with e.restrictScalars K intertwines T with X-multiplication
-- Uses AEval'.X_smul_of (X • of T v = of T (T v)) then e.map_smul to pull X out via K[X]-linearity.
theorem intertwine_x {K : Type*} [Field K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V) {r : ℕ} (f : Fin r → Polynomial K)
    (e : Module.AEval' T ≃ₗ[Polynomial K]
        DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i})) :
    ∀ v : V, ((Module.AEval'.of T).trans (e.restrictScalars K)) (T v)
      = ((LinearMap.lsmul (Polynomial K)
            (DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
            Polynomial.X).restrictScalars K)
          (((Module.AEval'.of T).trans (e.restrictScalars K)) v) := by
  intro v
  simp only [LinearEquiv.trans_apply, LinearMap.lsmul_apply,
             LinearMap.restrictScalars_apply]
  rw [← Module.AEval'.X_smul_of]
  exact e.map_smul Polynomial.X _

-- The `X`-scalar action on `⨁ᵢ K[X]/(fᵢ)` has matrix `blockDiagonal'` of the per-block
-- companion (`mulLeft (root fᵢ)`) matrices, in the `DFinsupp.basis` of power bases.
-- Entry-wise (`ext ⟨i,k⟩ ⟨j,l⟩`, `toMatrix_apply`): `dfinsupp_basis_repr_component` pushes
-- the `repr` into the `i`-th summand; then `by_cases i = j`. The diagonal entry is the
-- single-block companion value (`lsmul_x_diag_component` + `blockDiagonal'_apply_eq`); the
-- off-diagonal `repr` vanishes (`lsmul_x_offdiag_repr_zero` + `blockDiagonal'_apply_ne`)
-- because each cyclic summand is invariant under the `X`-action. Each sub-goal is a single
-- component identity over one (or two) summands — strictly smaller than the full matrix.
theorem block_diag {K : Type*} [Field K]
    {r : ℕ} (f : Fin r → Polynomial K) (hmonic : ∀ i, (f i).Monic) :
    LinearMap.toMatrix
        (DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis))
        (DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis))
        ((LinearMap.lsmul (Polynomial K)
            (DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))
            Polynomial.X).restrictScalars K)
      = Matrix.blockDiagonal' (fun i =>
          LinearMap.toMatrix (AdjoinRoot.powerBasis' (hmonic i)).basis
            (AdjoinRoot.powerBasis' (hmonic i)).basis
            (LinearMap.mulLeft K (AdjoinRoot.root (f i))))  := by
  ext ⟨i, k⟩ ⟨j, l⟩
  rw [LinearMap.toMatrix_apply]
  have hB := dfinsupp_basis_repr_component f hmonic
  rw [hB]
  have hdiag := lsmul_x_diag_component f hmonic
  have hoff := lsmul_x_offdiag_repr_zero f hmonic
  by_cases h : i = j
  · subst h
    rw [Matrix.blockDiagonal'_apply_eq, LinearMap.toMatrix_apply, LinearMap.mulLeft_apply]
    exact congrArg (fun w => (AdjoinRoot.powerBasis' (hmonic i)).basis.repr w k) (hdiag i l)
  · rw [Matrix.blockDiagonal'_apply_ne
      (fun i => LinearMap.toMatrix (AdjoinRoot.powerBasis' (hmonic i)).basis
        (AdjoinRoot.powerBasis' (hmonic i)).basis
        (LinearMap.mulLeft K (AdjoinRoot.root (f i)))) k l h]
    exact hoff j l i k h

end Library.LinearAlgebra.RationalCanonicalForm.DirectSumDecomp
