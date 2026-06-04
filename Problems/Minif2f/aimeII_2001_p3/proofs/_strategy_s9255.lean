import Mathlib
import Problems.Minif2f.aimeII_2001_p3.Defs
import Problems.Minif2f.aimeII_2001_p3.proofs.L_x_531_via_period
import Problems.Minif2f.aimeII_2001_p3.proofs.L_x_period_10

namespace Problems.Minif2f.aimeII_2001_p3

-- Decompose `x 531 = 211` via period-10: (1) Backward period lemma
-- `x (n+10) = x n` for n ≥ 1 (from the recurrence alone, via antiperiod-5
-- chained twice); (2) Builder reduction `x 531 = x 1` by induction on k in
-- `x (1 + 10*k) = x 1`, instantiated at k = 53. Closer: rewrite by reduction
-- and finish with h₀.
theorem s9255 (x : ℕ → ℤ) (h₀ : x 1 = 211) (h₂ : x 2 = 375) (h₃ : x 3 = 420) (h₄ : x 4 = 523) (h₆ : ∀ n ≥ 5, x n = x (n - 1) - x (n - 2) + x (n - 3) - x (n - 4)) : x 531 = 211  := by
  have h_period : ∀ n, 1 ≤ n → x (n + 10) = x n :=
    x_period_10 x h₀ h₂ h₃ h₄ h₆
  have h_reduce : x 531 = x 1 :=
    x_531_via_period x h₀ h₂ h₃ h₄ h₆ h_period
  linarith

end Problems.Minif2f.aimeII_2001_p3
