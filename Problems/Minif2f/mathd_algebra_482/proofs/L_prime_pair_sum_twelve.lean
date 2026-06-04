import Mathlib
import Problems.Minif2f.mathd_algebra_482.Defs

namespace Problems.Minif2f.mathd_algebra_482

-- prime_pair_sum_twelve: enumerate all (m,n) prime pairs with m+n=12 via double interval_cases + decide
-- Cases where m or n is non-prime are dispatched by `revert; decide`; sum forces the disjunct via omega
set_option linter.unusedVariables false in
set_option linter.style.longLine false in
theorem prime_pair_sum_twelve :
    ∀ (m n : ℕ) (k : ℝ) (f : ℝ → ℝ)
    (h₀ : Nat.Prime m) (h₁ : Nat.Prime n)
    (h₂ : ∀ x, f x = x ^ 2 - 12 * x + k)
    (h₃ : f m = 0) (h₄ : f n = 0)
    (h₅ : m ≠ n) (hsum : m + n = 12),
    (m = 5 ∧ n = 7) ∨ (m = 7 ∧ n = 5) := by
  intro m n k f h₀ h₁ h₂ h₃ h₄ h₅ hsum
  have hm : m ≤ 12 := by omega
  have hn : n ≤ 12 := by omega
  interval_cases m <;> interval_cases n <;>
    first
    | omega
    | (exfalso; revert h₀; decide)
    | (exfalso; revert h₁; decide)

end Problems.Minif2f.mathd_algebra_482
