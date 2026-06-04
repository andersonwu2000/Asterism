-- Split the conjunction into two independent bounds:
-- (1) lower_bound — `i < r`: if r ≤ i, then j := i mod r < i, r ∣ j²+j+p, IH gives
--     Nat.Prime (j²+j+p), forcing r = j²+j+p ≥ p ≥ r+2, contradiction.
-- (2) upper_bound — `r ≤ 2*i`: size analysis. If r > 2i then (2i+1)² ≤ r² ≤ i²+i+p
--     ⇒ 3i²+3i+1 ≤ p ⇒ i² < p/3, contradicting ⌊√(p/3)⌋ < i.
import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs._strategy_s9808

namespace Problems.Minif2f.imo_1987_p6

def bounds_r := @Problems.Minif2f.imo_1987_p6.s9808

end Problems.Minif2f.imo_1987_p6
