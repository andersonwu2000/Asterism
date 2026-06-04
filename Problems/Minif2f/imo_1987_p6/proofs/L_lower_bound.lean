-- Decompose `i < r` by contradiction: assume r ≤ i; take j := i mod r < r ≤ i.
-- Sub-goal `mod_dvd_witness` lifts r ∣ (i²+i+p) to r ∣ (j²+j+p) via congruence.
-- Sub-goal `size_clash_helper` packages the size argument (r prime divisor of a
-- prime number forces r = j²+j+p ≥ p, but r² ≤ i²+i+p ≤ (p-2)²+(p-2)+p < p²).
-- IH closes Nat.Prime (j²+j+p) from j < i ≤ p-2.
import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs._strategy_s9823

namespace Problems.Minif2f.imo_1987_p6

def lower_bound := @Problems.Minif2f.imo_1987_p6.s9823

end Problems.Minif2f.imo_1987_p6
