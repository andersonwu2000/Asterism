import Mathlib
namespace Problems.Minif2f.amc12b_2004_p3

-- lhs_two_val: split with padicValNat.mul, then prime_pow gives padicValNat 2 (2^x)=x
-- and padicValNat_prime_prime_pow gives padicValNat 2 (3^y)=0 (2≠3, both prime).
theorem lhs_two_val (x y : ℕ) : padicValNat 2 (2 ^ x * 3 ^ y) = x := by
  rw [padicValNat.mul (by positivity) (by positivity),
      padicValNat.prime_pow, padicValNat_prime_prime_pow y (by norm_num)]
  simp

end Problems.Minif2f.amc12b_2004_p3
