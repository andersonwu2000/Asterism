import Mathlib
import Problems.Minif2f.mathd_numbertheory_43.Defs
import Problems.Minif2f.mathd_numbertheory_43.proofs.L_pow_five_233_dvd_factorial_942
import Problems.Minif2f.mathd_numbertheory_43.proofs.L_pow_three_233_dvd_factorial_942

namespace Problems.Minif2f.mathd_numbertheory_43

-- Decompose 15^233 ∣ 942! via 15 = 3·5 and coprimality of 3^233, 5^233.
-- Sub-goals: 3^233 ∣ 942!  and  5^233 ∣ 942!  — each a single-prime power
-- divisibility (Legendre's formula). Combined by Nat.Coprime.mul_dvd_of_dvd_of_dvd
-- after rewriting 15^233 = 3^233 * 5^233.
theorem s9440 : 15 ^ 233 ∣ Nat.factorial 942  := by
  have h3 : (3 : ℕ) ^ 233 ∣ Nat.factorial 942 := pow_three_233_dvd_factorial_942
  have h5 : (5 : ℕ) ^ 233 ∣ Nat.factorial 942 := pow_five_233_dvd_factorial_942
  have hcop : Nat.Coprime ((3:ℕ)^233) ((5:ℕ)^233) :=
    (Nat.Coprime.pow_right 233 (Nat.Coprime.pow_left 233 (by decide : Nat.Coprime 3 5)))
  have hmul : (3:ℕ)^233 * 5^233 ∣ Nat.factorial 942 := hcop.mul_dvd_of_dvd_of_dvd h3 h5
  have heq : (15:ℕ)^233 = 3^233 * 5^233 := by rw [← Nat.mul_pow]
  rw [heq]; exact hmul

end Problems.Minif2f.mathd_numbertheory_43
