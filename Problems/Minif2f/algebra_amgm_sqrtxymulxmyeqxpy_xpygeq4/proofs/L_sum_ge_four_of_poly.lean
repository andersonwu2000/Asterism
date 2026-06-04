import Mathlib
namespace Problems.Minif2f.algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4

-- sum_ge_four_of_poly: derive x+y≥4 from xy(x-y)²=(x+y)² using (xy-1)(x+y)²=4(xy)² and (xy-2)²≥0
theorem sum_ge_four_of_poly : ∀ (x y : ℝ) (h₀ : 0 < x ∧ 0 < y) (h₁ : y ≤ x)
    (h_sq : x * y * (x - y)^2 = (x + y)^2),
    x + y ≥ 4 := by
  intro x y h₀ h₁ h_sq
  obtain ⟨hx, hy⟩ := h₀
  have hxy : (0 : ℝ) < x * y := mul_pos hx hy
  have hsum : (0 : ℝ) < x + y := by linarith
  have hkey : (x * y - 1) * (x + y) ^ 2 = 4 * (x * y) ^ 2 := by
    have hd : (x - y) ^ 2 = (x + y) ^ 2 - 4 * (x * y) := by ring
    nlinarith [sq_nonneg (x + y), sq_nonneg (x - y)]
  have hxygt1 : (1 : ℝ) < x * y := by nlinarith [sq_nonneg (x + y)]
  have hsqge : (x + y) ^ 2 ≥ 16 := by nlinarith [sq_nonneg (x * y - 2)]
  nlinarith [sq_nonneg (x + y - 4)]

end Problems.Minif2f.algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4
