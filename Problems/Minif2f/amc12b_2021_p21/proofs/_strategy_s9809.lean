import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_cube_lt_rhs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_quad_le_cube

namespace Problems.Minif2f.amc12b_2021_p21

-- Sandwich via the cube `t^3`: trivial polynomial step `3*t^2 ≤ t^3` (since t > 3)
-- bridges to the substantive cube-vs-double-exponential dominance `t^3 < RHS`.
-- Combine via `lt_of_le_of_lt` to get the strict bound `3*t^2 < RHS`.
theorem s9809 :
    ∀ t : ℝ, 3 < t →
      3 * t ^ 2 <
        Real.sqrt 2 ^ ((2 : ℝ) ^ t) * Real.log (Real.sqrt 2) *
          ((2 : ℝ) ^ t) * Real.log 2  := by
  intro t ht
  have h1 := quad_le_cube t ht
  have h2 := cube_lt_rhs t ht
  exact lt_of_le_of_lt h1 h2

end Problems.Minif2f.amc12b_2021_p21
