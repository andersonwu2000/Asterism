-- Construct the Vieta conjugate a' := k*b - a in ℕ.
-- Three sub-goals: (i) a ≤ k*b so ℕ subtraction agrees with ℤ;
-- (ii) the descent bound k*b - a ≤ b; (iii) the rewritten identity
-- b² + a'² = (b*a' + 1)*k. Pack the trio into the ⟨witness, le, eq⟩ triple.
import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs
import Problems.Minif2f.imo_1988_p6.proofs._strategy_s9711

namespace Problems.Minif2f.imo_1988_p6

def vieta_descent_witness := @Problems.Minif2f.imo_1988_p6.s9711

end Problems.Minif2f.imo_1988_p6
