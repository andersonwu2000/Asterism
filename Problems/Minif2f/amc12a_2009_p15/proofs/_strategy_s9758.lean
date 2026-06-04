import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_im_step_4n2

namespace Problems.Minif2f.amc12a_2009_p15

-- Induct on n. Base n=0: ∑ k ∈ Icc 1 2, k·I^k = I − 2, .im = 1 = 2·0+1.
-- Step k→k+1: the four extra terms (k₀∈{4k+3,…,4k+6}) contribute exactly +2 to .im
-- (the imag-part terms are −(4k+3) + (4k+5) = +2). Encapsulated as sub-goal `im_step_4n2`.
theorem s9758 : ∀ n : ℕ,
    (∑ k ∈ Finset.Icc (1 : ℕ) (4 * n + 2), (↑k : ℂ) * Complex.I ^ k).im
      = 2 * (n : ℝ) + 1  := by
  intro n
  have h_step := im_step_4n2
  induction n with
  | zero =>
    norm_num [Finset.sum_Icc_succ_top, Complex.ext_iff, Complex.I_sq, pow_succ]
  | succ k ih =>
    have h4 : 4 * (k + 1) + 2 = 4 * k + 2 + 4 := by ring
    rw [h4, h_step k, ih]
    push_cast; ring

end Problems.Minif2f.amc12a_2009_p15
