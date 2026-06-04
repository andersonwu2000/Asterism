import Mathlib
import Problems.Minif2f.amc12b_2004_p3.Defs
import Problems.Minif2f.amc12b_2004_p3.proofs.L_x_eq_four
import Problems.Minif2f.amc12b_2004_p3.proofs.L_y_eq_four

namespace Problems.Minif2f.amc12b_2004_p3

-- Split into two independent claims pinning x and y individually, combined by `omega`.
-- Sub-goal `x_eq_four`: x = 4 from 2^x * 3^y = 1296 (unique factorization on prime 2).
-- Sub-goal `y_eq_four`: y = 4 from 2^x * 3^y = 1296 (unique factorization on prime 3).
-- Each sub-goal is strictly simpler (one variable pinned, not a sum), and together pin x+y=8.
theorem s9254 : ∀ (x y : ℕ) (h₀ : 2 ^ x * 3 ^ y = 1296), x + y = 8  := by
  intro x y h₀
  have hx : x = 4 := x_eq_four x y h₀
  have hy : y = 4 := y_eq_four x y h₀
  omega

end Problems.Minif2f.amc12b_2004_p3
