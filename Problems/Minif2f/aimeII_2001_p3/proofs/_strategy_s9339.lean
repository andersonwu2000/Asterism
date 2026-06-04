import Mathlib
import Problems.Minif2f.aimeII_2001_p3.Defs
import Problems.Minif2f.aimeII_2001_p3.proofs.L_anti_period_5_2

namespace Problems.Minif2f.aimeII_2001_p3

-- Chain anti-period-5 twice: x(n+10) = x((n+5)+5) = -x(n+5) = -(-x n) = x n.
-- Single sub-goal `anti_period_5_2` (≥1, x(m+5) = -x m) — strictly simpler (2 unfoldings vs 10);
-- closer instantiates it at n and n+5 then `linarith`.
theorem s9339 (x : ℕ → ℤ) (h₀ : x 1 = 211) (h₂ : x 2 = 375) (h₃ : x 3 = 420)
    (h₄ : x 4 = 523)
    (h₆ : ∀ n ≥ 5, x n = x (n - 1) - x (n - 2) + x (n - 3) - x (n - 4)) :
    ∀ n, n ≥ 1 → x (n + 10) = x n  := by
  intro n hn
  have h_anti_period_5 := anti_period_5_2 x h₀ h₂ h₃ h₄ h₆
  have h1 := h_anti_period_5 n hn
  have h2 := h_anti_period_5 (n + 5) (by omega)
  have hEq : n + 5 + 5 = n + 10 := by omega
  rw [hEq] at h2
  linarith

end Problems.Minif2f.aimeII_2001_p3
