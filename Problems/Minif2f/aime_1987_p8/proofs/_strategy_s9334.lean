import Mathlib
import Problems.Minif2f.aime_1987_p8.Defs
import Problems.Minif2f.aime_1987_p8.proofs.L_real_bounds_of_nat_bounds

namespace Problems.Minif2f.aime_1987_p8

-- Witnesses k1 = ⌊6n/7⌋ + 1 and k2 = ⌊6n/7⌋ + 2 (Nat division). Both are
-- distinct (omega), satisfy the integer bounds 6n < 7k ∧ 8k < 7n for n ≥ 113
-- (omega via length-of-real-interval (6n/7, 7n/8) = n/56 > 2), and the
-- single sub-goal converts those Nat inequalities to the real division
-- inequalities (cross-multiplication using n+k > 0).
theorem s9334 (n : ℕ) (h : 113 ≤ n) :
    ∃ k1 k2 : ℕ, k1 ≠ k2 ∧
      ((8 : ℝ) / 15 < n / (n + k1) ∧ (n : ℝ) / (n + k1) < 7 / 13) ∧
      ((8 : ℝ) / 15 < n / (n + k2) ∧ (n : ℝ) / (n + k2) < 7 / 13)  := by
  have h_bridge := real_bounds_of_nat_bounds n h
  refine ⟨6 * n / 7 + 1, 6 * n / 7 + 2, by omega, ?_, ?_⟩
  · exact h_bridge _ (by omega) (by omega)
  · exact h_bridge _ (by omega) (by omega)

end Problems.Minif2f.aime_1987_p8
