import Mathlib
import Problems.Minif2f.amc12a_2008_p8.Defs
import Problems.Minif2f.amc12a_2008_p8.proofs.L_cube_eq_two_sqrt_two
import Problems.Minif2f.amc12a_2008_p8.proofs.L_x_sq_eq_two
import Problems.Minif2f.amc12a_2008_p8.proofs.L_y_eq_one

namespace Problems.Minif2f.amc12a_2008_p8

-- From y>0 and y^3=1 derive y=1; from 6x²=12y² and y=1 derive x²=2;
-- from x>0 and x²=2 derive x³=2√2. Each sub-goal drops one variable
-- or hypothesis, making it strictly simpler than the parent.
theorem s571 : ∀ (x y : ℝ) (h₀ : 0 < x ∧ 0 < y) (h₁ : y ^ 3 = 1)
    (h₂ : 6 * x ^ 2 = 2 * (6 * y ^ 2)), x ^ 3 = 2 * Real.sqrt 2 := by
  intro x y h₀ h₁ h₂
  obtain ⟨hx_pos, hy_pos⟩ := h₀
  have h_y_eq : y = 1 := y_eq_one y hy_pos h₁
  have h_xsq : x ^ 2 = 2 := x_sq_eq_two x y hx_pos h_y_eq h₂
  exact cube_eq_two_sqrt_two x hx_pos h_xsq

end Problems.Minif2f.amc12a_2008_p8
