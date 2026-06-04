-- Trichotomy on `n` versus `312`: split into `n < 312`, `n = 312`, `n > 312`.
-- Backward sub-goals bound the floor-log sum strictly below/above 1994 on the
-- two strict branches; combined with `hsum : sum = 1994`, both lead to omega
-- contradictions, so only the equality branch survives.
import Mathlib
import Problems.Minif2f.aime_1994_p4.Defs
import Problems.Minif2f.aime_1994_p4.proofs._strategy_s9275

namespace Problems.Minif2f.aime_1994_p4

def main := @Problems.Minif2f.aime_1994_p4.s9275

end Problems.Minif2f.aime_1994_p4
