-- Contrapositive: ¬(∃ n, f(f n) ≠ n+1987) ⇒ ∀ n, f(f n) = n+1987, contradicting no_such_fun.
-- Sub-goal `no_such_fun` carries the IMO 1987 P4 content (injectivity on ℕ + odd-modulus
-- involution counting on ℤ/1987); this Backward shell only reduces the ∃ to its negation.
import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs
import Problems.Minif2f.imo_1987_p4.proofs._strategy_s9293

namespace Problems.Minif2f.imo_1987_p4

def main := @Problems.Minif2f.imo_1987_p4.s9293

end Problems.Minif2f.imo_1987_p4
