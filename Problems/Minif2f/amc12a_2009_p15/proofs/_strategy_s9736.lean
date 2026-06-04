import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_re_step_4n3

namespace Problems.Minif2f.amc12a_2009_p15

-- Induct on n. Base n=0: ∑ k ∈ Icc 1 3, k·I^k = I - 2 - 3I, so .re = -2 = -(2·0+2).
-- Step k→k+1: the four extra terms (k₀∈{4k+4,…,4k+7}) contribute exactly -2 to .re
-- (the real-part terms are (4k+4) - (4k+6) = -2). Encapsulated as sub-goal `re_step_4n3`.
theorem s9736 : ∀ (n : ℕ),
    (∑ k ∈ Finset.Icc (1 : ℕ) (4 * n + 3), (↑k : ℂ) * Complex.I ^ k).re
      = -(2 * ((n : ℝ)) + 2)  := by
  intro n
  have h_step := re_step_4n3
  induction n with
  | zero =>
    norm_num [Finset.sum_Icc_succ_top, Complex.ext_iff, Complex.I_sq, pow_succ]
  | succ k ih =>
    have h4 : 4 * (k + 1) + 3 = 4 * k + 3 + 4 := by ring
    rw [h4, h_step k, ih]
    push_cast; ring

end Problems.Minif2f.amc12a_2009_p15
