-- Identify the LHS piecewise-FTC primitive as `α'(2·)` on the left half
-- via the proved sibling `flat_concat_ftc_left_half` (wrapped); change
-- variables `u = 2t` via the abstract substitution lemma matching the
-- open sibling `int_left_half_h_eq_alpha` (wrapped); smoothness comes
-- from `flat_concat_ftc_smooth` (wrapped). Closer is `exact` after `set`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10669

namespace Problems.residue_thm

def flat_ftc_left_half_int_eq := @Problems.residue_thm.s10669

end Problems.residue_thm
