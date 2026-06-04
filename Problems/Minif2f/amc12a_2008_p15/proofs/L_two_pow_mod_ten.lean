-- Decompose `2^m % 10 = 6` (for m % 4 = 0, 4 ≤ m) into a single periodic lemma:
-- ∀ k, 2^(4*k + 4) % 10 = 6 (provable by induction on k, base 2^4 = 16 % 10 = 6, step uses
-- pow_add + Nat.mul_mod). From m % 4 = 0 and 4 ≤ m, omega gives m = 4*(m/4 - 1) + 4,
-- and we apply the periodic lemma at k = m/4 - 1. Hypothesis hm10 is unused (parent over-supplies).
import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs
import Problems.Minif2f.amc12a_2008_p15.proofs._strategy_s9452

namespace Problems.Minif2f.amc12a_2008_p15

def two_pow_mod_ten := @Problems.Minif2f.amc12a_2008_p15.s9452

end Problems.Minif2f.amc12a_2008_p15
