import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs

namespace Problems.Minif2f.amc12a_2009_p15

-- at_97: norm_num expands sum via Icc_succ_top, splits re/im via ext_iff,
-- then evaluates I^k for all k using I_sq (I²=-1) + pow_succ recursion.
theorem at_97 : (∑ k ∈ Finset.Icc (1 : ℕ) 97, (↑k : ℂ) * Complex.I ^ k) =
    48 + 49 * Complex.I := by
  norm_num [Finset.sum_Icc_succ_top, Complex.ext_iff, Complex.I_sq, pow_succ]

end Problems.Minif2f.amc12a_2009_p15
