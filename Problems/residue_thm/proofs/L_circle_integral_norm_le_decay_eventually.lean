-- Decompose the cocompact decay bound into (A) a uniform bound for ‖f‖ on the
-- sphere S(z₀, R/2) (analytic ⇒ continuous on compact set), and (B) the
-- length×sup circle-integral estimate that promotes this uniform bound to
-- a cocompact-eventually inequality.
-- Combine: obtain C from A, then feed C into B.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10438

namespace Problems.residue_thm

def circle_integral_norm_le_decay_eventually := @Problems.residue_thm.s10438

end Problems.residue_thm
