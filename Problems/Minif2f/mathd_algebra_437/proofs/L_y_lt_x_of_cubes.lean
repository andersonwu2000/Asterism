import Mathlib
import Problems.Minif2f.mathd_algebra_437.Defs

namespace Problems.Minif2f.mathd_algebra_437

-- y_lt_x_of_cubes: cube function on ℝ is strictly monotone (Odd.strictMono_pow);
-- -101 < -45 gives y³ < x³, hence y < x
theorem y_lt_x_of_cubes :
    ∀ (x y : ℝ), x ^ 3 = -45 → y ^ 3 = -101 → y < x := by
  intro x y hx hy
  have h : y ^ 3 < x ^ 3 := by linarith
  exact (Odd.strictMono_pow (by norm_num : Odd 3)).lt_iff_lt.mp h

end Problems.Minif2f.mathd_algebra_437
