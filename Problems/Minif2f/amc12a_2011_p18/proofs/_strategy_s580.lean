import Mathlib
import Problems.Minif2f.amc12a_2011_p18.Defs
import Problems.Minif2f.amc12a_2011_p18.proofs.L_abs_x_le_one
import Problems.Minif2f.amc12a_2011_p18.proofs.L_abs_y_le_one

namespace Problems.Minif2f.amc12a_2011_p18

-- Decompose by extracting the L∞-bounds |x| ≤ 1 and |y| ≤ 1 from h₀,
-- then close x^2 - 6x + y^2 ≤ 8 by nlinarith on -1 ≤ x,y ≤ 1.
theorem s580 : ∀ (x y : ℝ) (h₀ : abs (x + y) + abs (x - y) = 2), x ^ 2 - 6 * x + y ^ 2 ≤ 8  := by
  intro x y h₀
  have hx : |x| ≤ 1 := abs_x_le_one x y h₀
  have hy : |y| ≤ 1 := abs_y_le_one x y h₀
  have hx' := abs_le.mp hx
  have hy' := abs_le.mp hy
  nlinarith [hx'.1, hx'.2, hy'.1, hy'.2,
    sq_nonneg (x - 1), sq_nonneg (x + 1),
    sq_nonneg (y - 1), sq_nonneg (y + 1)]

end Problems.Minif2f.amc12a_2011_p18
