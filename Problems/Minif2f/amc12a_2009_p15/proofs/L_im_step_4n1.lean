import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs

namespace Problems.Minif2f.amc12a_2009_p15

-- im_step_4n1: peel 4 top terms (k=4m+2..4m+5) via sum_Icc_succ_top, reduce I^(4m+j) via I^(4m)=1
-- Im contributions: 0, -(4m+3), 0, +(4m+5); net = +2.
theorem im_step_4n1 : ∀ m : ℕ,
    (∑ k ∈ Finset.Icc (1 : ℕ) (4 * m + 1 + 4), (↑k : ℂ) * Complex.I ^ k).im =
      (∑ k ∈ Finset.Icc (1 : ℕ) (4 * m + 1), (↑k : ℂ) * Complex.I ^ k).im + 2 := by
  intro m
  have h1 : (1 : ℕ) ≤ 4 * m + 1 + 1 := by omega
  have h2 : (1 : ℕ) ≤ 4 * m + 1 + 2 := by omega
  have h3 : (1 : ℕ) ≤ 4 * m + 1 + 3 := by omega
  have h4 : (1 : ℕ) ≤ 4 * m + 1 + 4 := by omega
  rw [show 4 * m + 1 + 4 = (4 * m + 1 + 3) + 1 from by ring]
  rw [Finset.sum_Icc_succ_top h4]
  rw [show 4 * m + 1 + 3 = (4 * m + 1 + 2) + 1 from by ring]
  rw [Finset.sum_Icc_succ_top h3]
  rw [show 4 * m + 1 + 2 = (4 * m + 1 + 1) + 1 from by ring]
  rw [Finset.sum_Icc_succ_top h2]
  rw [show 4 * m + 1 + 1 = (4 * m + 1) + 1 from by ring]
  rw [Finset.sum_Icc_succ_top h1]
  simp only [Complex.add_im, Complex.mul_im, Complex.natCast_re, Complex.natCast_im]
  have hI4m : Complex.I ^ (4 * m) = 1 := by
    rw [pow_mul]; norm_num [Complex.I_sq]
  rw [show 4 * m + 1 + 1 = 4 * m + 2 from by ring, pow_add, hI4m, one_mul,
      show 4 * m + 1 + 2 = 4 * m + 3 from by ring, pow_add, hI4m, one_mul,
      show 4 * m + 1 + 3 = 4 * m + 4 from by ring, pow_add, hI4m, one_mul,
      show 4 * m + 1 + 4 = 4 * m + 5 from by ring, pow_add, hI4m, one_mul]
  norm_num [Complex.I_re, Complex.I_im, Complex.I_sq, pow_succ]
  ring

end Problems.Minif2f.amc12a_2009_p15
