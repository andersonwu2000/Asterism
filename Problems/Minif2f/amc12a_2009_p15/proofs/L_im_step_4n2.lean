import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs

namespace Problems.Minif2f.amc12a_2009_p15

-- im_step_4n2: peel 4 terms {4m+3..4m+6} via sum_Icc_succ_top, I^(4m+3)=-I, im parts sum to +2
theorem im_step_4n2 : ∀ m : ℕ,
    (∑ k ∈ Finset.Icc (1 : ℕ) (4 * m + 2 + 4), (↑k : ℂ) * Complex.I ^ k).im =
      (∑ k ∈ Finset.Icc (1 : ℕ) (4 * m + 2), (↑k : ℂ) * Complex.I ^ k).im + 2 := by
  intro m
  have hI4 : Complex.I ^ 4 = 1 := by norm_num [pow_succ, Complex.I_sq]
  have hI4m : Complex.I ^ (4 * m) = 1 := by rw [pow_mul]; simp [hI4]
  have hI4m3 : Complex.I ^ (4 * m + 3) = -Complex.I := by
    rw [pow_add, hI4m, one_mul]; norm_num [pow_succ, Complex.I_sq]
  have hI4m4 : Complex.I ^ (4 * m + 4) = 1 := by
    rw [pow_add, hI4m]; simp [hI4]
  have hI4m5 : Complex.I ^ (4 * m + 5) = Complex.I := by
    rw [show 4 * m + 5 = 4 * m + 4 + 1 by omega, pow_succ, hI4m4, one_mul]
  have hI4m6 : Complex.I ^ (4 * m + 6) = -1 := by
    rw [show 4 * m + 6 = 4 * m + 4 + 2 by omega, pow_add, hI4m4]
    norm_num [pow_succ, Complex.I_sq]
  simp only [show 4 * m + 2 + 4 = 4 * m + 6 by omega]
  rw [show 4 * m + 6 = 4 * m + 5 + 1 by omega]
  rw [Finset.sum_Icc_succ_top (by omega : 1 ≤ 4 * m + 5 + 1)]
  rw [show 4 * m + 5 = 4 * m + 4 + 1 by omega]
  rw [Finset.sum_Icc_succ_top (by omega : 1 ≤ 4 * m + 4 + 1)]
  rw [show 4 * m + 4 = 4 * m + 3 + 1 by omega]
  rw [Finset.sum_Icc_succ_top (by omega : 1 ≤ 4 * m + 3 + 1)]
  rw [show 4 * m + 3 = 4 * m + 2 + 1 by omega]
  rw [Finset.sum_Icc_succ_top (by omega : 1 ≤ 4 * m + 2 + 1)]
  simp only [Complex.add_im]
  rw [hI4m3, hI4m4, hI4m5, hI4m6]
  simp [Complex.mul_im, Complex.one_re, Complex.one_im,
        Complex.I_re, Complex.I_im, Complex.neg_im]
  ring

end Problems.Minif2f.amc12a_2009_p15
