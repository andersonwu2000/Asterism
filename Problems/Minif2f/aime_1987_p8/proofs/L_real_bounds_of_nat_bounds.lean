import Mathlib
import Problems.Minif2f.aime_1987_p8.Defs

namespace Problems.Minif2f.aime_1987_p8

-- real_bounds_of_nat_bounds: cross-multiply nat bounds 6n<7k and 8k<7n
-- into real division inequalities 8/15 < n/(n+k) < 7/13 via div_lt_div_iff₀
theorem real_bounds_of_nat_bounds (n : ℕ) (h : 113 ≤ n) :
    ∀ k : ℕ, 6 * n < 7 * k → 8 * k < 7 * n →
      ((8 : ℝ) / 15 < n / (n + k) ∧ (n : ℝ) / (n + k) < 7 / 13) := by
  intro k h1 h2
  have hn : (0 : ℝ) < n := by exact_mod_cast Nat.pos_of_ne_zero (by omega)
  have hnk : (0 : ℝ) < n + k := by positivity
  have h1' : (6 : ℝ) * n < 7 * k := by exact_mod_cast h1
  have h2' : (8 : ℝ) * k < 7 * n := by exact_mod_cast h2
  refine ⟨?_, ?_⟩
  · rw [div_lt_div_iff₀ (by norm_num : (0:ℝ) < 15) hnk]
    nlinarith
  · rw [div_lt_div_iff₀ hnk (by norm_num : (0:ℝ) < 13)]
    nlinarith

end Problems.Minif2f.aime_1987_p8
