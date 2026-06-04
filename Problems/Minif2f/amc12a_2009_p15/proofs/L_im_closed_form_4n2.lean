-- Induct on n. Base n=0: ∑ k ∈ Icc 1 2, k·I^k = I − 2, .im = 1 = 2·0+1.
-- Step k→k+1: the four extra terms (k₀∈{4k+3,…,4k+6}) contribute exactly +2 to .im
-- (the imag-part terms are −(4k+3) + (4k+5) = +2). Encapsulated as sub-goal `im_step_4n2`.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9758

namespace Problems.Minif2f.amc12a_2009_p15

def im_closed_form_4n2 := @Problems.Minif2f.amc12a_2009_p15.s9758

end Problems.Minif2f.amc12a_2009_p15
