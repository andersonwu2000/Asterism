import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs

namespace Problems.Minif2f.amc12a_2009_p15

-- re_closed_form_4n1: induction on n; base by simp; step strips 4 top elements via
-- Finset.sum_Icc_succ_top, evaluates each I^(4n+r) via Complex.I_pow_eq_pow_mod, then
-- simplifies real parts and closes with push_cast + ring against the IH.
theorem re_closed_form_4n1 : ∀ n : ℕ,
    (∑ k ∈ Finset.Icc (1 : ℕ) (4 * n + 1), (↑k : ℂ) * Complex.I ^ k).re = 2 * (n : ℝ) := by
  intro n
  induction n with
  | zero => simp [Finset.Icc_self, Complex.I_re]
  | succ n ih =>
    rw [show 4 * (n + 1) + 1 = 4 * n + 4 + 1 from by omega,
        Finset.sum_Icc_succ_top (by omega : 1 ≤ 4 * n + 4 + 1),
        show 4 * n + 4 = 4 * n + 3 + 1 from by omega,
        Finset.sum_Icc_succ_top (by omega : 1 ≤ 4 * n + 3 + 1),
        show 4 * n + 3 = 4 * n + 2 + 1 from by omega,
        Finset.sum_Icc_succ_top (by omega : 1 ≤ 4 * n + 2 + 1),
        show 4 * n + 2 = 4 * n + 1 + 1 from by omega,
        Finset.sum_Icc_succ_top (by omega : 1 ≤ 4 * n + 1 + 1)]
    have hp2 : Complex.I ^ (4 * n + 1 + 1) = -1 := by
      rw [Complex.I_pow_eq_pow_mod, show (4 * n + 1 + 1) % 4 = 2 from by omega]
      exact Complex.I_sq
    have hp3 : Complex.I ^ (4 * n + 2 + 1) = -Complex.I := by
      rw [Complex.I_pow_eq_pow_mod, show (4 * n + 2 + 1) % 4 = 3 from by omega]
      exact Complex.I_pow_three
    have hp4 : Complex.I ^ (4 * n + 3 + 1) = 1 := by
      rw [Complex.I_pow_eq_pow_mod, show (4 * n + 3 + 1) % 4 = 0 from by omega]; norm_num
    have hp5 : Complex.I ^ (4 * n + 4 + 1) = Complex.I := by
      rw [Complex.I_pow_eq_pow_mod, show (4 * n + 4 + 1) % 4 = 1 from by omega]; norm_num
    rw [hp2, hp3, hp4, hp5]
    simp only [Complex.add_re, Complex.mul_re, Complex.neg_re, Complex.one_re,
               Complex.I_re, Complex.I_im, Complex.natCast_re, Complex.natCast_im,
               mul_neg, mul_one, mul_zero, neg_zero, sub_zero, add_zero, zero_mul, zero_sub,
               neg_mul, one_mul]
    push_cast [ih]
    ring

end Problems.Minif2f.amc12a_2009_p15
