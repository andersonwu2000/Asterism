-- Entrywise: rewrite `toMatrix … i j` to the power-basis repr coordinate, transport
-- that coordinate to the polynomial world `(X^(j+1) %ₘ f).coeff i` (h_repr_to_poly),
-- then compute that coefficient against the companion matrix entry (h_modByMonic_eq_companion).
import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs._strategy_s11589

namespace Problems.LinearAlgebra.rational_canonical_form

def companion_matrix_eq_tomatrix_mulx := @Problems.LinearAlgebra.rational_canonical_form.s11589

end Problems.LinearAlgebra.rational_canonical_form
