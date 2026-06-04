import Mathlib
import Problems.Minif2f.amc12b_2004_p3.Defs
import Problems.Minif2f.amc12b_2004_p3.proofs.L_lhs_two_val
import Problems.Minif2f.amc12b_2004_p3.proofs.L_rhs_two_val

namespace Problems.Minif2f.amc12b_2004_p3

-- Match 2-adic valuations on both sides of `2^x * 3^y = 1296`.
-- Sub-goal `lhs_two_val`: padicValNat 2 (2^x * 3^y) = x (since 2 ∤ 3).
-- Sub-goal `rhs_two_val`: padicValNat 2 1296 = 4 (decidable arithmetic).
-- Rewriting via h₀ and combining gives x = 4 by omega.
theorem s9345 : ∀ (x y : ℕ) (h₀ : 2 ^ x * 3 ^ y = 1296), x = 4  := by
  intro x y h₀
  have h_lhs := lhs_two_val x y
  have h_rhs := rhs_two_val
  rw [h₀] at h_lhs
  omega

end Problems.Minif2f.amc12b_2004_p3
