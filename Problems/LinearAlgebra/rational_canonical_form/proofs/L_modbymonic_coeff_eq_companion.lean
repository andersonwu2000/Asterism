-- Entrywise computation of `(X^(j+1) %ₘ f).coeff i`, split on whether the
-- exponent `j+1` is below `natDegree f` (low) or equals it (high).
-- Low: `X^(j+1) %ₘ f = X^(j+1)` (xpow_modbymonic_lt), coeff is `if i = j+1`.
-- High: `X^n %ₘ f = X^n - f` (xpow_modbymonic_self); coeff i = -f.coeff i.
-- Both reduce to `companionMatrix` via its definition + Fin bounds (omega).
import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs._strategy_s11590

namespace Problems.LinearAlgebra.rational_canonical_form

def modbymonic_coeff_eq_companion := @Problems.LinearAlgebra.rational_canonical_form.s11590

end Problems.LinearAlgebra.rational_canonical_form
