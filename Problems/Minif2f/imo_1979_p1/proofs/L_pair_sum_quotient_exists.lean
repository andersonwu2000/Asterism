-- Decomposition: bridge real-form denominators to nat-cast form, then assert numerator exists.
-- (A) sum_real_eq_sum_via_nat_cast: rewrite each `(660+(j:ℝ))*(1319-(j:ℝ))` as `(((660+j)*(1319-j) : ℕ) : ℝ)` (cast bridge).
-- (B) nat_recip_sum_quotient: ∃ n, nat-cast-form sum = n / (cast product). Combine via `obtain` + `Eq.trans`.
import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs._strategy_s9627

namespace Problems.Minif2f.imo_1979_p1

def pair_sum_quotient_exists := @Problems.Minif2f.imo_1979_p1.s9627

end Problems.Minif2f.imo_1979_p1
