import Mathlib
import Problems.Minif2f.aimeII_2001_p3.Defs
import Problems.Minif2f.aimeII_2001_p3.proofs.L_anti_period_5
import Problems.Minif2f.aimeII_2001_p3.proofs.L_value_x5

namespace Problems.Minif2f.aimeII_2001_p3

-- Decompose via 5-step anti-periodicity. Sub 1 establishes x(n+5) = -x(n)
-- for n ≥ 1 (2 applications of the recurrence); Sub 2 computes x(5) = 267.
-- Combinator: chain anti-period twice for x(n+10) = x(n), then iterate 97×.
theorem s772 (x : ℕ → ℤ) (h₀ : x 1 = 211) (h₂ : x 2 = 375) (h₃ : x 3 = 420) (h₄ : x 4 = 523) (h₆ : ∀ n ≥ 5, x n = x (n - 1) - x (n - 2) + x (n - 3) - x (n - 4)) : x 975 = 267  := by
  have h_anti : ∀ n, 1 ≤ n → x (n + 5) = -x n := anti_period_5 x h₀ h₂ h₃ h₄ h₆
  have h_base : x 5 = 267 := value_x5 x h₀ h₂ h₃ h₄ h₆
  have h_period : ∀ n, 1 ≤ n → x (n + 10) = x n := by
    intro n hn
    have h1 := h_anti n hn
    have h2 := h_anti (n + 5) (by omega)
    have h3 : n + 5 + 5 = n + 10 := by ring
    rw [h3] at h2
    linarith
  have h_iter : ∀ k : ℕ, x (5 + 10 * k) = x 5 := by
    intro k
    induction k with
    | zero => norm_num
    | succ k ih =>
      have hge : 1 ≤ 5 + 10 * k := by omega
      have hp := h_period (5 + 10 * k) hge
      have heq : 5 + 10 * (k + 1) = (5 + 10 * k) + 10 := by ring
      rw [heq, hp, ih]
  have h975 := h_iter 97
  have heq975 : (5 : ℕ) + 10 * 97 = 975 := by norm_num
  rw [heq975] at h975
  linarith

end Problems.Minif2f.aimeII_2001_p3
