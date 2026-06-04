-- Reduce disequality to strict comparison: show `√2^(2^y) < y^(2^√2)` on (√2, 3]
-- and close `≠` via `ne_of_gt`. The single sub-goal is strictly simpler than the
-- parent: a one-sided strict inequality instead of disequality, same hypothesis set.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9746

namespace Problems.Minif2f.amc12b_2021_p21

def no_root_between_sqrt2_and_three := @Problems.Minif2f.amc12b_2021_p21.s9746

end Problems.Minif2f.amc12b_2021_p21
