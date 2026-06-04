import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_rhs_dominates_above_4

namespace Problems.Minif2f.amc12b_2021_p21

-- Contrapositive: if y > 4, then RHS = √2^(2^y) strictly dominates
-- LHS = y^(2^√2) (double-exponential vs polynomial growth), so the
-- equation cannot hold. Single sub-goal isolates the strict bound on
-- (4, ∞); combinator discharges via `ne_of_lt` against `h_eq`.
theorem s9706 : ∀ y : ℝ, 0 < y → y ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ y → y ≤ 4 := by
  intro y hy h_eq
  by_contra h_not_le
  have h_gt : (4 : ℝ) < y := lt_of_not_ge h_not_le
  have h_strict := rhs_dominates_above_4 y h_gt
  exact absurd h_eq (ne_of_lt h_strict)

end Problems.Minif2f.amc12b_2021_p21
