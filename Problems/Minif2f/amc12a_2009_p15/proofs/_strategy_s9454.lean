import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_re_neq_48

namespace Problems.Minif2f.amc12a_2009_p15

-- Reduce complex inequality to real-part inequality: the sub-goal
-- `sum_re_neq_48` shows S(m).re ≠ 48 for any m > 97, while at m = 97 the real
-- part is exactly 48 (closed-form by norm_num via I_sq + pow_succ on the
-- finite Icc sum). Equality of the complex sums would force equality of real
-- parts, contradicting the sub-goal.
theorem s9454 : ∀ (m : ℕ), 97 < m →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k) ≠
    (∑ k ∈ Finset.Icc (1 : ℕ) 97, (↑k : ℂ) * Complex.I ^ k)  := by
  intro m hm habs
  have h_re_neq := sum_re_neq_48 m hm
  rw [habs] at h_re_neq
  apply h_re_neq
  norm_num [Finset.sum_Icc_succ_top, Complex.ext_iff, Complex.I_sq, pow_succ]

end Problems.Minif2f.amc12a_2009_p15
