-- Bound |x|,|y| ≤ 31 from x²+y²=1009 (sq_nonneg of the other), then
-- finite-box dispatch via interval_cases. sq_bound_1009 is a generic
-- abstract ℤ-bound lemma; int_box_dispatch_1009 carries bounds as hyps
-- so Builder can drive interval_cases / decide over the small finite box.
import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs
import Problems.Minif2f.imo_1977_p5.proofs._strategy_s9639

namespace Problems.Minif2f.imo_1977_p5

def int_sum_sq_1009 := @Problems.Minif2f.imo_1977_p5.s9639

end Problems.Minif2f.imo_1977_p5
