import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_prime_ge_five_not_two_sq_eq_one_2
import Problems.Minif2f.imo_1990_p3.proofs.L_two_sq_eq_one_given_no_seven_2

namespace Problems.Minif2f.imo_1990_p3

-- Decompose: assume p ∣ m, derive (2:ZMod p)^2 = 1 from the 7-free hypotheses
-- (gcd / ord-of-2 collapse — the hard direction), then close with the
-- companion contradiction `prime_ge_five_not_two_sq_eq_one_2`.
theorem s9848 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → ¬ p ∣ m  := by
  intro m hm hpow h3 h9 h7 p hp h5 hpm
  have h_two_sq := two_sq_eq_one_given_no_seven_2 m hm hpow h3 h9 h7 p hp h5 hpm
  exact prime_ge_five_not_two_sq_eq_one_2 m hm hpow h3 h9 p hp h5 h_two_sq

end Problems.Minif2f.imo_1990_p3
