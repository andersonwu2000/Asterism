import Mathlib
import Problems.Minif2f.algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4.Defs

namespace Problems.Minif2f.algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4

-- square_sqrt_eq: squaring h₂ via Real.sq_sqrt converts the sqrt equation to a polynomial identity
theorem square_sqrt_eq : ∀ (x y : ℝ) (h₀ : 0 < x ∧ 0 < y) (h₁ : y ≤ x)
    (h₂ : Real.sqrt (x * y) * (x - y) = x + y),
    x * y * (x - y)^2 = (x + y)^2 := by
  intro x y h₀ h₁ h₂
  have hxy : (0 : ℝ) ≤ x * y := le_of_lt (mul_pos h₀.1 h₀.2)
  have hsq : Real.sqrt (x * y) ^ 2 = x * y := Real.sq_sqrt hxy
  have h3 : (Real.sqrt (x * y) * (x - y)) ^ 2 = x * y * (x - y) ^ 2 := by
    have : (Real.sqrt (x * y)) ^ 2 = x * y := hsq
    nlinarith [sq_nonneg (Real.sqrt (x * y)), sq_nonneg (x - y)]
  have h4 : (Real.sqrt (x * y) * (x - y)) ^ 2 = (x + y) ^ 2 := by rw [h₂]
  linarith

end Problems.Minif2f.algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4
