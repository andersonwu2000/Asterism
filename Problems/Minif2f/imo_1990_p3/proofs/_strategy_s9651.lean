import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_eq_three_of_odd_no_large_prime
import Problems.Minif2f.imo_1990_p3.proofs.L_odd_of_sq_dvd_pow_succ

namespace Problems.Minif2f.imo_1990_p3

-- Abstract away the `n² ∣ 2ⁿ+1` hypothesis: it is only used to force `Odd n`.
-- (a) `odd_of_sq_dvd_pow_succ`: parity argument — already proved as `n_is_odd`.
-- (b) `eq_three_of_odd_no_large_prime`: with `Odd m` in place of the divisibility
--     hypothesis, the conclusion follows from `minFac`-style structure +
--     `3 ∣ m`, `¬ 9 ∣ m`, no prime ≥ 5 dividing `m`. Cleaner sub-goal shape.
theorem s9651 :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → ¬ (9 ∣ n) →
      (∀ p, Nat.Prime p → 5 ≤ p → ¬ p ∣ n) → n = 3  := by
  intro n hn hdvd h3 h9 hno
  have h_odd := odd_of_sq_dvd_pow_succ n hn hdvd
  exact eq_three_of_odd_no_large_prime n hn h_odd h3 h9 hno

end Problems.Minif2f.imo_1990_p3
