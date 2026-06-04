import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_im_step_4n3

namespace Problems.Minif2f.amc12a_2009_p15

-- Induct on n. Base n=0: ∑ k ∈ Icc 1 3, k·I^k has im = 1 + 0 + (-3) = -2 = -2·0 - 2.
-- Step k→k+1: four extra terms (k₀∈{4k+4..4k+7}) contribute -2 to .im. Encapsulated as `im_step_4n3`.
theorem s9761 : ∀ n : ℕ,
    (∑ k ∈ Finset.Icc (1 : ℕ) (4 * n + 3), (↑k : ℂ) * Complex.I ^ k).im
      = -2 * (n : ℝ) - 2  := by
  intro n
  have h_step := im_step_4n3
  induction n with
  | zero =>
    norm_num [Finset.sum_Icc_succ_top, Complex.ext_iff, Complex.I_sq, pow_succ]
  | succ k ih =>
    have h4 : 4 * (k + 1) + 3 = 4 * k + 3 + 4 := by ring
    rw [h4, h_step k, ih]
    push_cast; ring

end Problems.Minif2f.amc12a_2009_p15
