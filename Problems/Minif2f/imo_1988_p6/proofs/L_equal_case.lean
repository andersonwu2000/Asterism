import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs

namespace Problems.Minif2f.imo_1988_p6

-- equal_case: when b = a, equation 2a² = (a²+1)k forces k < 2 (nlinarith) and k > 0,
-- so k = 1; then a² = 1 and x = 1 witnesses k = 1²
theorem equal_case : ∀ (a k : ℕ), 0 < a → a^2 + a^2 = (a*a + 1) * k →
    ∃ x : ℕ, x^2 = k := by
  intro a k ha heq
  have haa : a * a = a ^ 2 := by ring
  rw [haa] at heq
  have hk_lt2 : k < 2 := by nlinarith [sq_nonneg a]
  have hk_pos : 0 < k := by
    rcases Nat.eq_zero_or_pos k with hk0 | hk
    · simp [hk0] at heq; linarith [sq_pos_of_pos ha]
    · exact hk
  have hk1 : k = 1 := by omega
  subst hk1
  exact ⟨1, by norm_num⟩

end Problems.Minif2f.imo_1988_p6
