import Mathlib
import Problems.Minif2f.mathd_numbertheory_326.Defs

namespace Problems.Minif2f.mathd_numbertheory_326

-- Direct integer proof: factor (n-1)n(n+1) - 720 = (n-9)(n² + 9n + 80); the quadratic factor is
-- always positive (discriminant -239), so n - 9 = 0, hence n + 1 = 10.
theorem s720 : ∀ (n : ℤ) (h₀ : (n - 1) * n * (n + 1) = 720 ), n + 1 = 10  := by
  intro n h₀
  have hfactor : (n - 9) * (n^2 + 9*n + 80) = 0 := by nlinarith [h₀, sq_nonneg n]
  have hquad_pos : (0 : ℤ) < n^2 + 9*n + 80 := by nlinarith [sq_nonneg (2*n + 9)]
  have hn9 : n - 9 = 0 := by
    rcases mul_eq_zero.mp hfactor with h | h
    · exact h
    · linarith
  linarith

end Problems.Minif2f.mathd_numbertheory_326
