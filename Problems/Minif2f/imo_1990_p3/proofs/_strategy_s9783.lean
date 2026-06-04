import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_exp_cube_succ
import Problems.Minif2f.imo_1990_p3.proofs.L_lifting_three_pow

namespace Problems.Minif2f.imo_1990_p3

-- Lift `3^(k+1) ∣ 2^(3^k*m)+1` to `3^(k+2) ∣ 2^(3^(k+1)*m)+1` via cube factorization.
-- Set a := 2^(3^k*m); reduce 2^(3^(k+1)*m) = a^3 (exp_cube_succ), then apply
-- the lifting lemma (lifting_three_pow): 3^(n+1) ∣ a+1 implies 3^(n+2) ∣ a^3+1.
theorem s9783 :
    ∀ (k m : ℕ), Odd m → ¬ (3 ∣ m) →
      3 ^ (k + 1) ∣ 2 ^ (3 ^ k * m) + 1 →
      3 ^ (k + 2) ∣ 2 ^ (3 ^ (k + 1) * m) + 1  := by
  intro k m hm hm3 h
  have h_exp := exp_cube_succ k m
  have h_pos : 1 ≤ 2 ^ (3 ^ k * m) := Nat.one_le_pow _ _ (by norm_num)
  rw [h_exp]
  exact lifting_three_pow _ _ h_pos h

end Problems.Minif2f.imo_1990_p3
