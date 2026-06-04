import Mathlib
import Problems.Minif2f.mathd_numbertheory_43.Defs
import Problems.Minif2f.mathd_numbertheory_43.proofs.L_pow_fifteen_233_dvd_factorial_942
import Problems.Minif2f.mathd_numbertheory_43.proofs.L_pow_fifteen_dvd_factorial_942_le_233

open Nat

namespace Problems.Minif2f.mathd_numbertheory_43

-- IsGreatest split: membership (15^233 ∣ 942!) ∧ upper bound (∀ n, 15^n ∣ 942! → n ≤ 233).
-- Both sub-goals are strictly simpler concrete divisibility / bounded quantifier statements.
theorem s9311 : IsGreatest { n : ℕ | 15 ^ n ∣ 942! } 233  := by
  have h_mem := pow_fifteen_233_dvd_factorial_942
  have h_ub := pow_fifteen_dvd_factorial_942_le_233
  exact ⟨h_mem, h_ub⟩

end Problems.Minif2f.mathd_numbertheory_43
