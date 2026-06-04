import Mathlib
import Problems.Minif2f.mathd_algebra_35.Defs

namespace Problems.Minif2f.mathd_algebra_35

-- Direct computation: q 2 = 6/2 = 3 via h₁ (with 2 ≠ 0), then p 3 = 2 - 3^2 = -7 via h₀.
-- Leaf-bypass: pure substitution + arithmetic, no sub-goals — `rw [h₀, h₁ 2 ...]; norm_num` closes it.
theorem s663 : ∀ (p q : ℝ → ℝ) (h₀ : ∀ x, p x = 2 - x ^ 2)
    (h₁ : ∀ x : ℝ, x ≠ 0 → q x = 6 / x), p (q 2) = -7 := by
  intro p q h₀ h₁
  rw [h₀, h₁ 2 (by norm_num)]
  norm_num

end Problems.Minif2f.mathd_algebra_35
