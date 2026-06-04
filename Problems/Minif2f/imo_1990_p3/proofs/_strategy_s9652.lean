import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_prime_ge_five_not_two_sq_eq_one
import Problems.Minif2f.imo_1990_p3.proofs.L_two_sq_eq_one_of_prime_ge_five_dvd

namespace Problems.Minif2f.imo_1990_p3

-- Order-of-2 contradiction: p ≥ 5 prime dividing n with n² ∣ 2ⁿ+1 forces
-- (2 : ZMod p)^2 = 1 (gcd(2n, p-1) = 2 from prime structure of n), which
-- gives p ∣ 3 contradicting p ≥ 5.
-- (A) `two_sq_eq_one_of_prime_ge_five_dvd` (Backward): the heart — packages
--     the order-of-2 / FLT / gcd chain into `(2 : ZMod p)^2 = 1` for any
--     p ≥ 5 prime dividing n.
-- (B) `prime_ge_five_not_two_sq_eq_one` (Builder): translation — 4 ≡ 1 (mod p)
--     means p ∣ 3, contradicting p ≥ 5 via `Nat.le_of_dvd` etc.
theorem s9652 :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → ¬ (9 ∣ n) →
      ∀ p, Nat.Prime p → 5 ≤ p → ¬ p ∣ n  := by
  intro n hn hsq h3 h9 p hp hp5 hpn
  have h1 := two_sq_eq_one_of_prime_ge_five_dvd n hn hsq h3 h9 p hp hp5 hpn
  exact prime_ge_five_not_two_sq_eq_one n hn hsq h3 h9 p hp hp5 h1

end Problems.Minif2f.imo_1990_p3
