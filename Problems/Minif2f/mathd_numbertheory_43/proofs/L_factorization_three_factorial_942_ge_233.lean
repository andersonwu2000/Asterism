import Mathlib
import Problems.Minif2f.mathd_numbertheory_43.Defs

namespace Problems.Minif2f.mathd_numbertheory_43

-- factorization_three_factorial_942_ge_233: v₃(942!) = 467 ≥ 233 via Legendre's formula
-- Nat.factorization_factorial rewrites to ∑ i ∈ Ico 1 7, 942 / 3^i = 467; decide closes.
theorem factorization_three_factorial_942_ge_233 :
    (233 : ℕ) ≤ (Nat.factorial 942).factorization 3 := by
  rw [Nat.factorization_factorial (by decide : Nat.Prime 3) (by norm_num : Nat.log 3 942 < 7)]
  decide

end Problems.Minif2f.mathd_numbertheory_43
