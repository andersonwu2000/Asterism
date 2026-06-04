import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_no_prime_ge_five_dvd_given_no_seven_2

namespace Problems.Minif2f.imo_1990_p3

-- Conclusion is vacuous: under the parent hypotheses, no prime ≥ 5 can divide m.
-- Sub-goal supplies `¬ p ∣ m`, which contradicts the binder hypothesis `p ∣ m`;
-- the divisibility conclusion then follows by `absurd`.
theorem s9839 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ m → Nat.gcd (2 * m) (p - 1) ∣ 2  := by
  intro m hm hdvd h3 h9 h7 p hp h5 hpm
  have h_no_prime_ge_five_dvd_given_no_seven :=
    no_prime_ge_five_dvd_given_no_seven_2 m hm hdvd h3 h9 h7 p hp h5
  exact absurd hpm h_no_prime_ge_five_dvd_given_no_seven

end Problems.Minif2f.imo_1990_p3
