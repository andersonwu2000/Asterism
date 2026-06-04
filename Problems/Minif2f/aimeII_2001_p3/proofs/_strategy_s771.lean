import Mathlib
import Problems.Minif2f.aimeII_2001_p3.Defs
import Problems.Minif2f.aimeII_2001_p3.proofs.L_periodicity_10

namespace Problems.Minif2f.aimeII_2001_p3

-- Decompose via period-10: extract x(n+10) = x(n) for n ≥ 1 as a sub-goal,
-- then iterate by induction on k to reduce x 753 = x (3 + 10*75) = x 3 = 420.
theorem s771 (x : ℕ → ℤ) (h₀ : x 1 = 211) (h₂ : x 2 = 375) (h₃ : x 3 = 420)
    (h₄ : x 4 = 523)
    (h₆ : ∀ n ≥ 5, x n = x (n - 1) - x (n - 2) + x (n - 3) - x (n - 4)) :
    x 753 = 420 := by
  have hper : ∀ n, n ≥ 1 → x (n + 10) = x n := periodicity_10 x h₀ h₂ h₃ h₄ h₆
  have key : ∀ k : ℕ, x (3 + 10 * k) = 420 := by
    intro k
    induction k with
    | zero => simpa using h₃
    | succ k ih =>
      have heq : 3 + 10 * (k + 1) = (3 + 10 * k) + 10 := by ring
      rw [heq, hper (3 + 10 * k) (by omega)]
      exact ih
  have hnum : (753 : ℕ) = 3 + 10 * 75 := by norm_num
  rw [hnum]
  exact key 75

end Problems.Minif2f.aimeII_2001_p3
