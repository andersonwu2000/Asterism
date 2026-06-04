import Mathlib
import Problems.Minif2f.aime_1988_p4.Defs
import Problems.Minif2f.aime_1988_p4.proofs.L_nineteen_le_sum_abs
import Problems.Minif2f.aime_1988_p4.proofs.L_sum_abs_lt_card

namespace Problems.Minif2f.aime_1988_p4

-- Sandwich 19 < (n:ℝ) between two real-valued bounds on Σ|aₖ|, then cast.
-- (a) sum_abs_lt_card: Σ|aₖ| < (n:ℝ), since each |aₖ| < 1 and h₁ rules out n=0.
-- (b) nineteen_le_sum_abs: 19 ≤ Σ|aₖ|, since h₁ gives Σ|aₖ| = 19 + |Σaₖ| ≥ 19.
-- Chain: lt_of_le_of_lt → (19:ℝ) < (n:ℝ) → 19 < n in ℕ → omega closes 20 ≤ n.
theorem s785 : ∀ (n : ℕ) (a : ℕ → ℝ) (h₀ : ∀ n, abs (a n) < 1) (h₁ : (∑ k ∈ Finset.range n, abs (a k)) = 19 + abs (∑ k ∈ Finset.range n, a k)), 20 ≤ n  := by
  intro n a h₀ h₁
  have h_sum_abs_lt_card := sum_abs_lt_card n a h₀ h₁
  have h_nineteen_le_sum_abs := nineteen_le_sum_abs n a h₀ h₁
  have h_lt : (19 : ℝ) < (n : ℝ) := lt_of_le_of_lt h_nineteen_le_sum_abs h_sum_abs_lt_card
  have h_nat : 19 < n := by exact_mod_cast h_lt
  omega

end Problems.Minif2f.aime_1988_p4
