import Mathlib
import Problems.Minif2f.mathd_algebra_482.Defs

namespace Problems.Minif2f.mathd_algebra_482

-- sum_roots_eq_twelve: subtract the two root equations to factor (m-n)(m+n-12)=0,
-- then m≠n forces m+n=12 via mul_eq_zero
theorem sum_roots_eq_twelve : ∀ (m n : ℕ) (k : ℝ) (f : ℝ → ℝ) (h₀ : Nat.Prime m)
    (h₁ : Nat.Prime n) (h₂ : ∀ x, f x = x ^ 2 - 12 * x + k) (h₃ : f m = 0) (h₄ : f n = 0)
    (h₅ : m ≠ n), m + n = 12 := by
  intro m n k f _ _ h₂ h₃ h₄ h₅
  have hm : (m : ℝ) ^ 2 - 12 * m + k = 0 := by
    have := h₃; rw [h₂] at this; exact this
  have hn : (n : ℝ) ^ 2 - 12 * n + k = 0 := by
    have := h₄; rw [h₂] at this; exact this
  have hfact : ((m : ℝ) - n) * ((m : ℝ) + n - 12) = 0 := by linear_combination hm - hn
  rcases mul_eq_zero.mp hfact with h | h
  · exfalso
    have heq : (m : ℝ) = n := by linarith
    exact h₅ (by exact_mod_cast heq)
  · exact_mod_cast (show (m : ℝ) + n = 12 by linarith)

end Problems.Minif2f.mathd_algebra_482
