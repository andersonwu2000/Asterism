import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_n_ne_zero_from_lcm_gcd
import Problems.Minif2f.amc12a_2020_p21.proofs.L_pow_three_two_dvd

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Reduce `3 ≤ n.factorization 2` to (a) 2^3 ∣ n and (b) n ≠ 0, then close
-- via `Nat.Prime.pow_dvd_iff_le_factorization` on the prime 2. The
-- divisibility carries the 2-adic arithmetic content from the lcm/gcd
-- equation; n ≠ 0 is a side-condition extractable directly from the lcm
-- equation (mirrors the sibling strategy s9795 for prime 5).
theorem s9800 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      3 ≤ n.factorization 2  := by
  intro n h
  have h_dvd := pow_three_two_dvd n h
  have h_nz := n_ne_zero_from_lcm_gcd n h
  exact (Nat.Prime.pow_dvd_iff_le_factorization Nat.prime_two h_nz).mp h_dvd
end Problems.Minif2f.amc12a_2020_p21
