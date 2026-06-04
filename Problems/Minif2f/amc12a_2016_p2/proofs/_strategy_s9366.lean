import Mathlib
import Problems.Minif2f.amc12a_2016_p2.Defs
import Problems.Minif2f.amc12a_2016_p2.proofs.L_powers_combine
import Problems.Minif2f.amc12a_2016_p2.proofs.L_pow_eq_gives_three

namespace Problems.Minif2f.amc12a_2016_p2

-- Split into 2 sub-goals: (A) algebraic combine `10^x * 100^(2x) = 10^(5x)`,
-- (B) injectivity finisher `10^(5x) = 1000^5 → x = 3`. Combinator: rewrite h₀
-- via (A), then apply (B). Each piece is strictly simpler: (A) is pure rpow
-- arithmetic with `100 = 10^2`, (B) is `1000^5 = 10^15` + rpow injectivity at base 10.
theorem s9366 : ∀ (x : ℝ) (h₀ : (10 : ℝ) ^ x * 100 ^ (2 * x) = 1000 ^ 5), x = 3  := by
  intro x h₀
  have h_powers_combine := powers_combine x
  rw [h_powers_combine] at h₀
  exact pow_eq_gives_three x h₀

end Problems.Minif2f.amc12a_2016_p2
