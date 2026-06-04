import Mathlib
import Problems.Minif2f.aimeII_2001_p3.Defs

namespace Problems.Minif2f.aimeII_2001_p3

-- entry_kind: Builder
theorem anti_period_5_2 (x : ℕ → ℤ) (h₀ : x 1 = 211) (h₂ : x 2 = 375) (h₃ : x 3 = 420)
    (h₄ : x 4 = 523)
    (h₆ : ∀ n ≥ 5, x n = x (n - 1) - x (n - 2) + x (n - 3) - x (n - 4)) :
    ∀ n, 1 ≤ n → x (n + 5) = -x n := by grind

end Problems.Minif2f.aimeII_2001_p3
