import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_false_of_prime_ne_seven_dvd

namespace Problems.Minif2f.imo_1990_p3

-- Case-split on whether the candidate prime equals 7.
-- The p = 7 case contradicts ¬ 7 ∣ m directly via h7.
-- Otherwise, defer to a Backward sub-goal that carries the explicit p ≠ 7
-- hypothesis, letting the eventual derivation pivot to q := Nat.minFac (m / 3)
-- (the smallest prime factor of m strictly above 3) instead of running the
-- gcd / order argument on the arbitrary p (which is the dead `s9848` shape).
theorem s9852 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → ¬ p ∣ m  := by
  intro m hm hdvd h3 h9 h7 p hp h5 hpm
  by_cases hp7 : p = 7
  · subst hp7
    exact h7 hpm
  · exact (false_of_prime_ne_seven_dvd m hm hdvd h3 h9 h7 p hp h5 hp7 hpm).elim

end Problems.Minif2f.imo_1990_p3
