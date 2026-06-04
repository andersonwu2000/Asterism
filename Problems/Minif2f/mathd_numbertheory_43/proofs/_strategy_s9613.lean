import Mathlib
import Problems.Minif2f.mathd_numbertheory_43.Defs
import Problems.Minif2f.mathd_numbertheory_43.proofs.L_five_pow_dvd_factorial_942_le_233

namespace Problems.Minif2f.mathd_numbertheory_43

-- Reduce 15-adic upper bound to 5-adic upper bound via `5 ∣ 15` and `pow_dvd_pow_of_dvd`.
-- v₅(942!) = 188+37+7+1 = 233 is tight (v₃(942!) = 467 is slack), so the 5-adic side
-- exactly captures the bound; one strictly simpler sub-goal on a single prime.
theorem s9613 : ∀ n : ℕ, 15 ^ n ∣ Nat.factorial 942 → n ≤ 233  := by
  intro n hn
  have h_five_bound := five_pow_dvd_factorial_942_le_233
  have h5n : (5:ℕ)^n ∣ Nat.factorial 942 :=
    dvd_trans (pow_dvd_pow_of_dvd (by norm_num : (5:ℕ) ∣ 15) n) hn
  exact h_five_bound n h5n

end Problems.Minif2f.mathd_numbertheory_43
