-- Reduce to abstract change-of-variables wrapper `subst_alpha_step_wrapper`
-- (mirrors the open sibling `int_left_half_h_eq_alpha` shape). The wrapper
-- consumes only `hα'`, `hh`, `hh_left`; remaining parent hypotheses are
-- unused at this layer. The Builder will close the wrapper via the open
-- sibling once it lands; meanwhile the wrapper is a strictly-simpler
-- sub-goal carrying no `Q`-analyticity / `β'` / endpoint-derivative data.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10675

namespace Problems.residue_thm

def flat_left_int_subst_alpha_wrap := @Problems.residue_thm.s10675

end Problems.residue_thm
