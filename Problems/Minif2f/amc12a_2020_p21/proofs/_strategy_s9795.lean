import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_nonzero_of_lcm_gcd_eq
import Problems.Minif2f.amc12a_2020_p21.proofs.L_pow_three_five_dvd
open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Split `3 ≤ n.factorization 5` into (a) 5^3 ∣ n and (b) n ≠ 0, then close
-- via `Nat.Prime.pow_dvd_iff_le_factorization` on the prime 5. The divisibility
-- claim isolates the arithmetic content (lcm/gcd ↔ 5-adic valuation), while
-- n ≠ 0 is a side-condition extracted from the lcm equation.
theorem s9795 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      3 ≤ n.factorization 5  := by
  intro n h
  have h_dvd := pow_three_five_dvd n h
  have h_nz := nonzero_of_lcm_gcd_eq n h
  have hp5 : (5 : ℕ).Prime := by decide
  exact (Nat.Prime.pow_dvd_iff_le_factorization hp5 h_nz).mp h_dvd

end Problems.Minif2f.amc12a_2020_p21
