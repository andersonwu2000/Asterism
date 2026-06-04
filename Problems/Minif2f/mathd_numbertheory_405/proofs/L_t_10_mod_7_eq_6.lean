import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs

namespace Problems.Minif2f.mathd_numbertheory_405

-- t_10_mod_7_eq_6: Fibonacci recurrence unrolled 10 steps; 55 % 7 = 6 closed by omega.
theorem t_10_mod_7_eq_6 (b : ℕ) (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1)
    (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) (h₄ : b ≡ 10 [MOD 16]) :
    t 10 % 7 = 6 := by
  have h2 : t 2 = t 0 + t 1 := h₂ 2 (by norm_num)
  have h3 : t 3 = t 1 + t 2 := h₂ 3 (by norm_num)
  have h4 : t 4 = t 2 + t 3 := h₂ 4 (by norm_num)
  have h5 : t 5 = t 3 + t 4 := h₂ 5 (by norm_num)
  have h6 : t 6 = t 4 + t 5 := h₂ 6 (by norm_num)
  have h7 : t 7 = t 5 + t 6 := h₂ 7 (by norm_num)
  have h8 : t 8 = t 6 + t 7 := h₂ 8 (by norm_num)
  have h9 : t 9 = t 7 + t 8 := h₂ 9 (by norm_num)
  have h10 : t 10 = t 8 + t 9 := h₂ 10 (by norm_num)
  omega

end Problems.Minif2f.mathd_numbertheory_405
