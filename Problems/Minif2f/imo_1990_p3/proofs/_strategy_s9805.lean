import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_exp_cube_succ
import Problems.Minif2f.imo_1990_p3.proofs.L_three_lte_lifting
import Problems.Minif2f.imo_1990_p3.proofs.L_cube_lte_upper

namespace Problems.Minif2f.imo_1990_p3

-- Cube-lift the contrapositive of the LTE-3 step. With a := 2^(3^k*m), reduce
-- 2^(3^(k+1)*m) to a^3 (exp_cube_succ), supply the lower bound 3^(k+1) ∣ a+1 from
-- three_lte_lifting, then apply cube_lte_upper (dual of lifting_three_pow:
-- given 3^(k+1) ∣ a+1 and ¬ 3^(k+2) ∣ a+1, conclude ¬ 3^(k+3) ∣ a^3+1).
theorem s9805 :
    ∀ (k m : ℕ), Odd m → ¬ (3 ∣ m) →
      (¬ 3 ^ (k + 2) ∣ 2 ^ (3 ^ k * m) + 1) →
      ¬ 3 ^ (k + 1 + 2) ∣ 2 ^ (3 ^ (k + 1) * m) + 1  := by
  intro k m hm hm3 hk
  have h_exp := exp_cube_succ k m
  have h_pos : 1 ≤ 2 ^ (3 ^ k * m) := Nat.one_le_pow _ _ (by norm_num)
  have h_low := three_lte_lifting k m hm hm3
  have h_cube := cube_lte_upper (2 ^ (3 ^ k * m)) k h_pos h_low hk
  rw [h_exp]
  exact h_cube

end Problems.Minif2f.imo_1990_p3
