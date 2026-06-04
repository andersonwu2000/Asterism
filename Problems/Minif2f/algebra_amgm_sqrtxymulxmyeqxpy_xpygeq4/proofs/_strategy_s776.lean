import Mathlib
import Problems.Minif2f.algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4.Defs
import Problems.Minif2f.algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4.proofs.L_square_sqrt_eq
import Problems.Minif2f.algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4.proofs.L_sum_ge_four_of_poly

namespace Problems.Minif2f.algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4

-- Decomposition: square h₂ to clear `Real.sqrt`, then nlinarith on the polynomial form.
-- (1) `square_sqrt_eq` lifts `√(xy) · (x-y) = x+y` to `x*y*(x-y)^2 = (x+y)^2` via `Real.sq_sqrt`.
-- (2) `sum_ge_four_of_poly` derives `x+y ≥ 4` from that identity using `(xy-2)^2 ≥ 0`.
theorem s776 : ∀ (x y : ℝ) (h₀ : 0 < x ∧ 0 < y) (h₁ : y ≤ x)
    (h₂ : Real.sqrt (x * y) * (x - y) = x + y), x + y ≥ 4  := by
  intro x y h₀ h₁ h₂
  have h_sq : x * y * (x - y)^2 = (x + y)^2 := square_sqrt_eq x y h₀ h₁ h₂
  exact sum_ge_four_of_poly x y h₀ h₁ h_sq

end Problems.Minif2f.algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4
