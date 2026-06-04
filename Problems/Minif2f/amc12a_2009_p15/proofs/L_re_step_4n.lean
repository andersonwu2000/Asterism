import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs

namespace Problems.Minif2f.amc12a_2009_p15

-- re_step_4n: peel 4 top terms via sum_Icc_succ_top, use I^(4m)=1, norm_num on I^1..I^4 real parts
-- The four extra terms k=4m+1..4m+4 contribute re-parts 0, -(4m+2), 0, (4m+4), summing to 2.
theorem re_step_4n : ∀ m : ℕ,
    (∑ k ∈ Finset.Icc (1 : ℕ) (4 * m + 4), (↑k : ℂ) * Complex.I ^ k).re =
      (∑ k ∈ Finset.Icc (1 : ℕ) (4 * m), (↑k : ℂ) * Complex.I ^ k).re + 2 := by
  intro m
  have h1 : (1 : ℕ) ≤ 4 * m + 1 := by omega
  have h2 : (1 : ℕ) ≤ 4 * m + 2 := by omega
  have h3 : (1 : ℕ) ≤ 4 * m + 3 := by omega
  have h4 : (1 : ℕ) ≤ 4 * m + 4 := by omega
  rw [show 4 * m + 4 = (4 * m + 3) + 1 from by ring]
  rw [Finset.sum_Icc_succ_top h4]
  rw [show 4 * m + 3 = (4 * m + 2) + 1 from by ring]
  rw [Finset.sum_Icc_succ_top h3]
  rw [show 4 * m + 2 = (4 * m + 1) + 1 from by ring]
  rw [Finset.sum_Icc_succ_top h2]
  rw [show 4 * m + 1 = (4 * m) + 1 from by ring]
  rw [Finset.sum_Icc_succ_top h1]
  simp only [Complex.add_re, Complex.mul_re, Complex.natCast_re, Complex.natCast_im]
  have hI4m : Complex.I ^ (4 * m) = 1 := by
    rw [pow_mul]; norm_num [Complex.I_sq]
  rw [show 4 * m + 1 = 4 * m + 1 from rfl, pow_add, hI4m, one_mul,
      show 4 * m + 1 + 1 = 4 * m + 2 from by ring, pow_add, hI4m, one_mul,
      show 4 * m + 1 + 1 + 1 = 4 * m + 3 from by ring, pow_add, hI4m, one_mul,
      show 4 * m + 1 + 1 + 1 + 1 = 4 * m + 4 from by ring, pow_add, hI4m, one_mul]
  norm_num [Complex.I_re, Complex.I_im, Complex.I_sq, pow_succ]
  ring

end Problems.Minif2f.amc12a_2009_p15
