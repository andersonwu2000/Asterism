import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs

namespace Problems.Minif2f.mathd_numbertheory_405

-- t_5_mod_7_eq_5: unfold Fibonacci recurrence five steps from h₀/h₁/h₂ to get t 5 = 5
theorem t_5_mod_7_eq_5 : ∀ (a : ℕ) (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1)
    (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) (h₃ : a ≡ 5 [MOD 16]),
    t 5 % 7 = 5 := by
  intro a t h₀ h₁ h₂ _
  have ht2 : t 2 = 1 := by rw [h₂ 2 (by norm_num), h₀, h₁]
  have ht3 : t 3 = 2 := by rw [h₂ 3 (by norm_num), h₁, ht2]
  have ht4 : t 4 = 3 := by rw [h₂ 4 (by norm_num), ht2, ht3]
  have ht5 : t 5 = 5 := by rw [h₂ 5 (by norm_num), ht3, ht4]
  rw [ht5]

end Problems.Minif2f.mathd_numbertheory_405
