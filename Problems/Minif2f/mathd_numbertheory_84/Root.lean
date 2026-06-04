-- Direct numeric proof: 9/160 * 100 = 5.625, so ⌊5.625⌋ = 5.
-- Reduce via `Int.floor_eq_iff` to the bracketing `5 ≤ 5.625 < 6`; both inequalities
-- discharge by `norm_num` on rational arithmetic. No sub-goals required.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_84.Defs
import Problems.Minif2f.mathd_numbertheory_84.proofs._strategy_s747

namespace Problems.Minif2f.mathd_numbertheory_84

def main := @Problems.Minif2f.mathd_numbertheory_84.s747

end Problems.Minif2f.mathd_numbertheory_84
