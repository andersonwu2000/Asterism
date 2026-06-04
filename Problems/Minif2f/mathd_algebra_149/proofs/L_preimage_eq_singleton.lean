import Mathlib
import Problems.Minif2f.mathd_algebra_149.Defs

namespace Problems.Minif2f.mathd_algebra_149

-- preimage_eq_singleton: Set.ext + case split on x < -5; nlinarith kills the quadratic branch,
-- linarith closes the linear branch, and norm_num confirms f(6)=10.
theorem preimage_eq_singleton (f : ℝ → ℝ) (h₀ : ∀ x < -5, f x = x ^ 2 + 5)
    (h₁ : ∀ x ≥ -5, f x = 3 * x - 8) : f ⁻¹' {10} = ({6} : Set ℝ) := by
  ext x
  simp only [Set.mem_preimage, Set.mem_singleton_iff]
  constructor
  · intro hfx
    by_cases hx : x < -5
    · have heq := h₀ x hx
      rw [heq] at hfx
      nlinarith [sq_nonneg x]
    · simp only [not_lt] at hx
      have heq := h₁ x hx
      rw [heq] at hfx
      linarith
  · intro hx
    subst hx
    have h6 : (6 : ℝ) ≥ -5 := by norm_num
    rw [h₁ 6 h6]
    norm_num

end Problems.Minif2f.mathd_algebra_149
