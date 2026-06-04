-- Induct on n. Base n=0: ∑ k ∈ Icc 1 1, k·I^k = I, so .im = 1 = 2·0+1.
-- Step k→k+1: four extra terms (k₀∈{4k+2..4k+5}) contribute +2 to .im.
-- Encapsulated as sub-goal `im_step_4n1`.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9757

namespace Problems.Minif2f.amc12a_2009_p15

def closed_form_im_mod1 := @Problems.Minif2f.amc12a_2009_p15.s9757

end Problems.Minif2f.amc12a_2009_p15
