import Mathlib
import Problems.Minif2f.mathd_algebra_282.Defs

namespace Problems.Minif2f.mathd_algebra_282

theorem main : ∀ (f : ℝ → ℝ) (h₀ : ∀ x : ℝ, ¬ (Irrational x) → f x = abs (Int.floor x)) (h₁ : ∀ x, Irrational x → f x = (Int.ceil x) ^ 2), f (8 ^ (1 / 3)) + f (-Real.pi) + f (Real.sqrt 50) + f (9 / 2) = 79 := by sorry

end Problems.Minif2f.mathd_algebra_282
