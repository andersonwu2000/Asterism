import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs

namespace Problems.Minif2f.imo_1988_p6

-- lift_quot_eq: cast ℕ multiplicative identity x²·(ab+1)=a²+b² to ℝ division equality
-- Uses eq_div_iff after norm_cast establishes ab+1≠0; exact_mod_cast closes the cast goal.
set_option linter.style.longLine false in
theorem lift_quot_eq : ∀ (a b : ℕ) (_h₀ : 0 < a ∧ 0 < b) (_h₁ : a * b + 1 ∣ a ^ 2 + b ^ 2)
    (x : ℕ), x ^ 2 * (a * b + 1) = a ^ 2 + b ^ 2 →
    (x ^ 2 : ℝ) = (a ^ 2 + b ^ 2) / (a * b + 1) := by
  intro a b _h₀ _h₁ x hx
  have hab : (a * b + 1 : ℝ) ≠ 0 := by norm_cast
  rw [eq_div_iff hab]
  exact_mod_cast hx

end Problems.Minif2f.imo_1988_p6
