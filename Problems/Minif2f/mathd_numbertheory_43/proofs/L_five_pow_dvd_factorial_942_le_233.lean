import Mathlib
import Problems.Minif2f.mathd_numbertheory_43.Defs

namespace Problems.Minif2f.mathd_numbertheory_43

-- five_pow_dvd_factorial_942_le_233: upper bound via Legendre formula v5(942!) = 233
-- factorization_factorial rewrites (942!).factorization 5 as a concrete Ico sum,
-- then decide closes the numeric equality; omega finishes from hkey.
theorem five_pow_dvd_factorial_942_le_233 : ∀ n : ℕ, 5 ^ n ∣ Nat.factorial 942 → n ≤ 233 := by
  intro n h
  have h5 : Nat.Prime 5 := by norm_num
  have hkey : n ≤ (Nat.factorial 942).factorization 5 :=
    (h5.pow_dvd_iff_le_factorization (Nat.factorial_ne_zero 942)).mp h
  have hval : (Nat.factorial 942).factorization 5 = 233 := by
    rw [Nat.factorization_factorial h5 (by norm_num : Nat.log 5 942 < 5)]
    decide
  omega

end Problems.Minif2f.mathd_numbertheory_43
