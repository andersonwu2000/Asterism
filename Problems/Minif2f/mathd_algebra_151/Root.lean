-- Split `⌈√27⌉ - ⌊√26⌋ = 1` into two leaf integer computations.
-- Sub-goals: `ceil_sqrt_27_eq_six` (⌈√27⌉ = 6) and `floor_sqrt_26_eq_five`
-- (⌊√26⌋ = 5). Each is a closed arithmetic fact (no parent binders to thread).
-- Combine by rewriting both into the LHS; `norm_num` closes `6 - 5 = 1`.
import Mathlib
import Problems.Minif2f.mathd_algebra_151.Defs
import Problems.Minif2f.mathd_algebra_151.proofs._strategy_s9300

namespace Problems.Minif2f.mathd_algebra_151

def main := @Problems.Minif2f.mathd_algebra_151.s9300

end Problems.Minif2f.mathd_algebra_151
