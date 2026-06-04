import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs

namespace Problems.LinearAlgebra.rational_canonical_form

-- entry_kind: Builder
-- repr_mulleft_basis_eq_modbymonic: the powerBasis' repr of mulLeft(root f)(basis j) equals
-- (X^(j+1) %ₘ f).coeff i, using powerBasisAux'_repr_apply_to_fun + modByMonicHom_mk
theorem repr_mulleft_basis_eq_modbymonic {K : Type*} [Field K] {f : Polynomial K}
    (hf : f.Monic) (i j : Fin f.natDegree) :
    (AdjoinRoot.powerBasis' hf).basis.repr
      (LinearMap.mulLeft K (AdjoinRoot.root f) ((AdjoinRoot.powerBasis' hf).basis j)) i
      = (Polynomial.X ^ ((j : ℕ) + 1) %ₘ f).coeff i := by
  have h1 : (AdjoinRoot.powerBasis' hf).basis j = AdjoinRoot.root f ^ (j : ℕ) :=
    (AdjoinRoot.powerBasis' hf).basis_eq_pow j
  rw [h1, LinearMap.mulLeft_apply]
  have h2 : AdjoinRoot.root f * AdjoinRoot.root f ^ (j : ℕ) =
      AdjoinRoot.root f ^ ((j : ℕ) + 1) := by ring
  rw [h2]
  rw [show (AdjoinRoot.powerBasis' hf).basis.repr = (AdjoinRoot.powerBasisAux' hf).repr from rfl]
  change (AdjoinRoot.modByMonicHom hf (AdjoinRoot.root f ^ ((j : ℕ) + 1))).coeff ↑i =
      (Polynomial.X ^ ((j : ℕ) + 1) %ₘ f).coeff ↑i
  have h3 : AdjoinRoot.root f ^ ((j : ℕ) + 1) =
      AdjoinRoot.mk f (Polynomial.X ^ ((j : ℕ) + 1)) := by
    rw [← AdjoinRoot.mk_X (f := f), ← map_pow]
  rw [h3, AdjoinRoot.modByMonicHom_mk]

end Problems.LinearAlgebra.rational_canonical_form
