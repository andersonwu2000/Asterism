import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_eq_seven_of_prime_ge_five_two_pow_six
import Problems.Minif2f.imo_1990_p3.proofs.L_min_fac_div_three_prime_ge_five_2

namespace Problems.Minif2f.imo_1990_p3

-- Reduce to a pure ZMod statement: q := Nat.minFac (m/3) is prime ≥ 5
-- (sub-goal `min_fac_div_three_prime_ge_five_2`, identical to an already-proved
-- lemma — framework alias resolves it). With that primality + range data, the
-- sub-goal `eq_seven_of_prime_ge_five_two_pow_six` packages the ZMod →
-- ℕ-divisibility bridge (q ∣ 63) and the prime classification: q = 7.
theorem s9864 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      (2 : ZMod (Nat.minFac (m / 3)))^6 = 1 →
      Nat.minFac (m / 3) = 7 := by
  intro m hm2 hdvd h3m h9m h7m p hp h5p h7p hpm h26
  have h_pge : Nat.Prime (Nat.minFac (m / 3)) ∧ 5 ≤ Nat.minFac (m / 3) :=
    min_fac_div_three_prime_ge_five_2 m hm2 hdvd h3m h9m h7m p hp h5p h7p hpm
  exact eq_seven_of_prime_ge_five_two_pow_six (Nat.minFac (m / 3)) h_pge.1 h_pge.2 h26

end Problems.Minif2f.imo_1990_p3
