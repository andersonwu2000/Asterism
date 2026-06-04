-- Vieta jump: construct the conjugate root a' (= k·b - a in ℤ) as a ℕ with the
-- descent inequality a' ≤ b and the matching identity b² + a'² = (b·a' + 1)·k.
-- Combinator splits on a' = 0 (forcing k = b², perfect-square branch witnessed by b)
-- vs 0 < a' (descent witnessed by (c, d) = (b, a'); c < a follows from b < a).
import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs
import Problems.Minif2f.imo_1988_p6.proofs._strategy_s9674

namespace Problems.Minif2f.imo_1988_p6

def vieta_step := @Problems.Minif2f.imo_1988_p6.s9674

end Problems.Minif2f.imo_1988_p6
