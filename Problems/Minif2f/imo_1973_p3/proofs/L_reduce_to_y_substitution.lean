-- Substitution y = x + 1/x: from a real root x of the quartic, build y.
-- (1) x ≠ 0 (else equation reads 1 = 0); (2) (x+1/x)^2 ≥ 4 (AM-GM on x^2, 1/x^2);
-- (3) divide quartic by x^2: a*(x+1/x) + b = 2 - (x+1/x)^2. Combine via ⟨x+1/x, _, _⟩.
import Mathlib
import Problems.Minif2f.imo_1973_p3.Defs
import Problems.Minif2f.imo_1973_p3.proofs._strategy_s9323

namespace Problems.Minif2f.imo_1973_p3

def reduce_to_y_substitution := @Problems.Minif2f.imo_1973_p3.s9323

end Problems.Minif2f.imo_1973_p3
