import Mathlib
import Problems.Minif2f.mathd_numbertheory_43.Defs
import Problems.Minif2f.mathd_numbertheory_43.proofs.L_factorization_three_factorial_942_ge_233

namespace Problems.Minif2f.mathd_numbertheory_43

-- Reduce `3^233 ∣ 942!` to a factorization lower bound via Legendre's formula:
-- `Nat.Prime.pow_dvd_iff_le_factorization` converts `p^k ∣ n!` to
-- `k ≤ n!.factorization p`. v₃(942!) = 467, so 233 is well below the tight bound;
-- the remaining sub-goal is a pure numerical valuation computation.
theorem s9626 : (3 : ℕ) ^ 233 ∣ Nat.factorial 942  := by
  have h : (233 : ℕ) ≤ (Nat.factorial 942).factorization 3 :=
    factorization_three_factorial_942_ge_233
  exact (Nat.Prime.pow_dvd_iff_le_factorization
    (by decide : Nat.Prime 3) (Nat.factorial_ne_zero 942)).mpr h

end Problems.Minif2f.mathd_numbertheory_43
