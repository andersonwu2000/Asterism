import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_modbymonic_coeff_eq_companion
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_repr_mulleft_basis_eq_modbymonic

namespace Problems.LinearAlgebra.rational_canonical_form

-- Entrywise: rewrite `toMatrix … i j` to the power-basis repr coordinate, transport
-- that coordinate to the polynomial world `(X^(j+1) %ₘ f).coeff i` (h_repr_to_poly),
-- then compute that coefficient against the companion matrix entry (h_modByMonic_eq_companion).
theorem s11589 {K : Type*} [Field K] {f : Polynomial K}
    (hf : f.Monic) :
    LinearMap.toMatrix (AdjoinRoot.powerBasis' hf).basis (AdjoinRoot.powerBasis' hf).basis
        (LinearMap.mulLeft K (AdjoinRoot.root f))
      = companionMatrix f  := by
  ext i j
  have h_repr_to_poly := repr_mulleft_basis_eq_modbymonic hf i j
  have h_modByMonic_eq_companion := modbymonic_coeff_eq_companion hf i j
  rw [LinearMap.toMatrix_apply, h_repr_to_poly, h_modByMonic_eq_companion]

end Problems.LinearAlgebra.rational_canonical_form
