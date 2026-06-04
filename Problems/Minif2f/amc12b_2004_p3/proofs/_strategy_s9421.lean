import Mathlib
import Problems.Minif2f.amc12b_2004_p3.Defs
import Problems.Minif2f.amc12b_2004_p3.proofs.L_lhs_three_val
import Problems.Minif2f.amc12b_2004_p3.proofs.L_rhs_three_val

namespace Problems.Minif2f.amc12b_2004_p3

-- Match 3-adic valuations on both sides of `2^x * 3^y = 1296`.
-- Sub-goal `lhs_three_val`: padicValNat 3 (2^x * 3^y) = y (since 3 ∤ 2).
-- Sub-goal `rhs_three_val`: padicValNat 3 1296 = 4 (decidable arithmetic).
-- Rewriting via h₀ and combining gives y = 4 by omega.
theorem s9421 : ∀ (x y : ℕ) (h₀ : 2 ^ x * 3 ^ y = 1296), y = 4  := by
  intro x y h₀
  have h_lhs := lhs_three_val x y
  have h_rhs := rhs_three_val
  rw [h₀] at h_lhs
  omega

end Problems.Minif2f.amc12b_2004_p3
