-- Decompose `(m^2 + 2^m) % 10 = 6` (for m % 10 = 0, m % 4 = 0, 4 ≤ m) into:
-- (1) `m^2 % 10 = 0` (uses m % 10 = 0), (2) `2^m % 10 = 6` (uses m % 4 = 0 ∧ 4 ≤ m).
-- omega closes `(m^2 + 2^m) % 10 = 6` from the two mod facts.
import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs
import Problems.Minif2f.amc12a_2008_p15.proofs._strategy_s9368

namespace Problems.Minif2f.amc12a_2008_p15

def combine_mod_pow_abs := @Problems.Minif2f.amc12a_2008_p15.s9368

end Problems.Minif2f.amc12a_2008_p15
