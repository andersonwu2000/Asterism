-- Collapse 2^n mod 7 down to its representative on n % 3, then check k < 3.
-- mod_collapse: 7 ∣ 2^n - 1 ⇒ 7 ∣ 2^(n%3) - 1 (uses 2^3 ≡ 1 mod 7).
-- small_zero:   only k = 0 in {0,1,2} satisfies 7 ∣ 2^k - 1 (k=1,2 vacuous).
-- Combining gives n % 3 = 0, i.e. 3 ∣ n.
import Mathlib
import Problems.Minif2f.imo_1964_p1_1.Defs
import Problems.Minif2f.imo_1964_p1_1.proofs._strategy_s9261

namespace Problems.Minif2f.imo_1964_p1_1

def main := @Problems.Minif2f.imo_1964_p1_1.s9261

end Problems.Minif2f.imo_1964_p1_1
