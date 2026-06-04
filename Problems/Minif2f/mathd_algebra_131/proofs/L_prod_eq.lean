import Mathlib
import Problems.Minif2f.mathd_algebra_131.Defs

namespace Problems.Minif2f.mathd_algebra_131

-- entry_kind: Builder
theorem prod_eq : ∀ (a b : ℝ) (f : ℝ → ℝ) (h₀ : ∀ x, f x = 2 * x ^ 2 - 7 * x + 2)
    (h₁ : f a = 0) (h₂ : f b = 0) (h₃ : a ≠ b), a * b = 1 := by grind

end Problems.Minif2f.mathd_algebra_131
