-- Compute `HasDerivWithinAt H (deriv-formula) (Icc 0 1) s` via product/chain/FTC
-- (`h_chain`), then reduce the formula to `0` algebraically using `γ s - a ≠ 0`
-- (`h_zero`); rewrite and convert to `derivWithin = 0` via `uniqueDiffOn_Icc_zero_one`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10304

namespace Problems.residue_thm

def deriv_exp_neg_path_zero := @Problems.residue_thm.s10304

end Problems.residue_thm
