import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs

namespace Problems.Minif2f.imo_1979_p1

-- two_mul_recip_two_j_eq_recip_j: Finset.mul_sum pulls 2 inside; push_cast + field_simp close
-- each term: 2 * (1 / (2 * j)) = 1 / j, using j ≥ 1 for nonzero denominator.
theorem two_mul_recip_two_j_eq_recip_j :
    (2 : ℝ) * (∑ j ∈ Finset.Icc (1 : ℕ) 659, ((1 : ℝ) / ((2 * j : ℕ) : ℝ))) =
      (∑ j ∈ Finset.Icc (1 : ℕ) 659, ((1 : ℝ) / (j : ℝ))) := by
  rw [Finset.mul_sum]
  apply Finset.sum_congr rfl
  intro j hj
  simp only [Finset.mem_Icc] at hj
  have hj0 : (j : ℝ) ≠ 0 := by exact_mod_cast (show j ≠ 0 by omega)
  push_cast
  field_simp [hj0]

end Problems.Minif2f.imo_1979_p1
