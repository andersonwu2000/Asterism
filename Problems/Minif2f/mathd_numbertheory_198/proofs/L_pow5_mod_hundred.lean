import Mathlib
namespace Problems.Minif2f.mathd_numbertheory_198

-- pow5_mod_hundred: 5^n % 100 = 25 for all n ≥ 2, proved by induction on k with n = 2 + k;
-- step uses Nat.mul_mod to reduce (5^(2+k) * 5) % 100 via the IH value 25.
theorem pow5_mod_hundred : ∀ n : ℕ, 2 ≤ n → 5 ^ n % 100 = 25 := by
  intro n hn
  obtain ⟨k, rfl⟩ := Nat.exists_eq_add_of_le hn
  induction k with
  | zero => norm_num
  | succ k ih =>
    rw [show 2 + (k + 1) = (2 + k) + 1 by omega, pow_succ, Nat.mul_mod, ih]
    norm_num

end Problems.Minif2f.mathd_numbertheory_198
