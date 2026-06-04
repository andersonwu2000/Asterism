-- Induct on n. Base n=0: Icc 1 0 is empty, so sum.im = 0 = -2·0.
-- Step k→k+1: the four extra terms (k₀∈{4k+1,4k+2,4k+3,4k+4}) contribute
-- exactly -2 to the imaginary part (i² = −1, i⁴ = 1; the two imag-part terms are
-- (4k+1) - (4k+3) = -2). Encapsulate as one sub-goal `im_step_4n`.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9756

namespace Problems.Minif2f.amc12a_2009_p15

def closed_form_im_mod0 := @Problems.Minif2f.amc12a_2009_p15.s9756

end Problems.Minif2f.amc12a_2009_p15
