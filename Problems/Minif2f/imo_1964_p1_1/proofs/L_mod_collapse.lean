-- Iterate the period lemma 7 ∣ 2^(m+3) - 1 → 7 ∣ 2^m - 1 by induction on k.
-- period_iter: ∀ m k, 7 ∣ 2^(m + 3*k) - 1 → 7 ∣ 2^m - 1 (induct on k).
-- Apply with m = n%3, k = n/3, using Nat.mod_add_div : n%3 + 3*(n/3) = n.
import Mathlib
import Problems.Minif2f.imo_1964_p1_1.Defs
import Problems.Minif2f.imo_1964_p1_1.proofs._strategy_s9351

namespace Problems.Minif2f.imo_1964_p1_1

def mod_collapse := @Problems.Minif2f.imo_1964_p1_1.s9351

end Problems.Minif2f.imo_1964_p1_1
