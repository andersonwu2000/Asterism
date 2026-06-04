import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_eq_three_of_odd_no_large_prime
import Problems.Minif2f.imo_1990_p3.proofs.L_odd_of_sq_dvd_pow_succ

namespace Problems.Minif2f.imo_1990_p3

-- eq_three_of_no_large_prime_2: reduce to Odd n via odd_of_sq_dvd_pow_succ,
-- then close with eq_three_of_odd_no_large_prime.
theorem eq_three_of_no_large_prime_2 :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → ¬ (9 ∣ n) →
      (∀ p, Nat.Prime p → 5 ≤ p → ¬ p ∣ n) → n = 3 := by
  intro n hn hdvd h3 h9 hno
  have h_odd := odd_of_sq_dvd_pow_succ n hn hdvd
  exact eq_three_of_odd_no_large_prime n hn h_odd h3 h9 hno

end Problems.Minif2f.imo_1990_p3
