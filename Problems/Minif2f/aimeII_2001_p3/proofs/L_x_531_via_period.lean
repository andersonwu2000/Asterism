import Mathlib
import Problems.Minif2f.aimeII_2001_p3.Defs

namespace Problems.Minif2f.aimeII_2001_p3

-- x_531_via_period: reduce x 531 = x 1 by period-10 induction (k=53)
-- Prove ∀ k, x (1 + 10 * k) = x 1 by induction; instantiate at k = 53 since 531 = 1 + 10 * 53.
theorem x_531_via_period (x : ℕ → ℤ) (h₀ : x 1 = 211) (h₂ : x 2 = 375) (h₃ : x 3 = 420)
    (h₄ : x 4 = 523)
    (h₆ : ∀ n ≥ 5, x n = x (n - 1) - x (n - 2) + x (n - 3) - x (n - 4))
    (h_period : ∀ n, 1 ≤ n → x (n + 10) = x n) :
    x 531 = x 1 := by
  have key : ∀ k : ℕ, x (1 + 10 * k) = x 1 := by
    intro k
    induction k with
    | zero => simp
    | succ n ih =>
      have h1 : 1 + 10 * (n + 1) = (1 + 10 * n) + 10 := by ring
      rw [h1]
      rw [h_period (1 + 10 * n) (by omega)]
      exact ih
  have h531 : 531 = 1 + 10 * 53 := by norm_num
  rw [h531]
  exact key 53

end Problems.Minif2f.aimeII_2001_p3
