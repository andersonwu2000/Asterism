import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs

set_option maxHeartbeats 0

namespace Problems.Minif2f.amc12a_2009_p15

-- sum_at_97_closed_form: norm_num unrolls ∑ k·Iᵏ (k=1..97) via Icc_succ_top + I_sq + pow_succ
theorem sum_at_97_closed_form :
    (∑ k ∈ Finset.Icc (1 : ℕ) 97, (↑k : ℂ) * Complex.I ^ k) = 48 + 49 * Complex.I := by
  norm_num [Finset.sum_Icc_succ_top, Complex.ext_iff, Complex.I_sq, pow_succ]

end Problems.Minif2f.amc12a_2009_p15
