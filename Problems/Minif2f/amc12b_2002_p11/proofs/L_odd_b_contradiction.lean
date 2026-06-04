import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs

namespace Problems.Minif2f.amc12b_2002_p11

-- odd_b_contradiction: if b is an odd prime, parity forces contradiction
-- via Nat.Prime.eq_two_or_odd on a: when a=2 the subtraction underflows to 0
-- (Nat.not_prime_zero); when a is odd, a+b is even and ≥6 so not prime
-- (Nat.Prime.eq_one_or_self_of_dvd with 2 | a+b).
theorem odd_b_contradiction : ∀ (a b : ℕ), Nat.Prime a → Nat.Prime b →
    Nat.Prime (a + b) → Nat.Prime (a - b) → b % 2 = 1 → False := by
  intro a b ha hb h_sum h_diff h_odd
  have hb_ge3 : 3 ≤ b := by have := hb.two_le; omega
  rcases ha.eq_two_or_odd with rfl | ha_odd
  · have hab : 2 - b = 0 := by omega
    rw [hab] at h_diff
    exact Nat.not_prime_zero h_diff
  · have ha_ge3 : 3 ≤ a := by have := ha.two_le; omega
    have hdvd : 2 ∣ a + b := by
      rw [Nat.dvd_iff_mod_eq_zero]; omega
    rcases h_sum.eq_one_or_self_of_dvd 2 hdvd with h | h
    · exact absurd h (by norm_num)
    · omega

end Problems.Minif2f.amc12b_2002_p11
