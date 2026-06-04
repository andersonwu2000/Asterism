import Mathlib
namespace Problems.Minif2f.mathd_numbertheory_43

-- five_factorization_factorial_942_ge_233: Legendre formula gives v₅(942!) = 233 ≥ 233
-- Rewrites via Nat.factorization_factorial to ∑ i ∈ Ico 1 5, 942 / 5^i, then closes by decide.
theorem five_factorization_factorial_942_ge_233 :
    233 ≤ (Nat.factorial 942).factorization 5 := by
  have h : (Nat.factorial 942).factorization 5 = 233 := by
    rw [Nat.factorization_factorial (by norm_num : Nat.Prime 5)
        (by norm_num : Nat.log 5 942 < 5)]
    decide
  linarith

end Problems.Minif2f.mathd_numbertheory_43
