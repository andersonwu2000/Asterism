import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_dfinsupp_basis_repr_component
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_lsmul_x_diag_component
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_lsmul_x_offdiag_repr_zero

namespace Problems.LinearAlgebra.rational_canonical_form

-- The `X`-scalar action on `⨁ᵢ K[X]/(fᵢ)` has matrix `blockDiagonal'` of the per-block
-- companion (`mulLeft (root fᵢ)`) matrices, in the `DFinsupp.basis` of power bases.
-- Entry-wise (`ext ⟨i,k⟩ ⟨j,l⟩`, `toMatrix_apply`): `dfinsupp_basis_repr_component` pushes
-- the `repr` into the `i`-th summand; then `by_cases i = j`. The diagonal entry is the
-- single-block companion value (`lsmul_x_diag_component` + `blockDiagonal'_apply_eq`); the
-- off-diagonal `repr` vanishes (`lsmul_x_offdiag_repr_zero` + `blockDiagonal'_apply_ne`)
-- because each cyclic summand is invariant under the `X`-action. Each sub-goal is a single
-- component identity over one (or two) summands — strictly smaller than the full matrix.
theorem s11595 {K : Type*} [Field K]
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

end Problems.LinearAlgebra.rational_canonical_form
