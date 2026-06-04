import Mathlib
import Problems.Minif2f.amc12a_2010_p11.Defs
import Problems.Minif2f.amc12a_2010_p11.proofs.L_b_eq_eight_seventh
import Problems.Minif2f.amc12a_2010_p11.proofs.L_eight_over_seven_pow_eq

namespace Problems.Minif2f.amc12a_2010_p11

-- Decomposition: (i) algebraically rewrite h₁ to (8/7)^x = 7^7;
-- (ii) combine with h₀, h₂ to pin b = 8/7 via logb/rpow injectivity.
-- Both sub-goals strip the logb wrapping or the mixed-base power; each
-- is strictly smaller than the parent statement.
theorem s9280 : ∀ (x b : ℝ) (h₀ : 0 < b) (h₁ : (7 : ℝ) ^ (x + 7) = 8 ^ x)
    (h₂ : x = Real.logb b (7 ^ 7)), b = 8 / 7 := by
  intro x b h₀ h₁ h₂
  have h_pow := eight_over_seven_pow_eq x h₁
  exact b_eq_eight_seventh x b h₀ h_pow h₂

end Problems.Minif2f.amc12a_2010_p11
