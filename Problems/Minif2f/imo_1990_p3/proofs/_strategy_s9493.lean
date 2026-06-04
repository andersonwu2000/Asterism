import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_coprime_n_min_fac_pred
import Problems.Minif2f.imo_1990_p3.proofs.L_min_fac_dvd_three_with_coprime

namespace Problems.Minif2f.imo_1990_p3

-- Decompose via order-of-2 mod p := minFac n: the order divides 2, forcing p ∣ 3.
-- (a) `coprime_n_min_fac_pred`: gcd(n, p-1) = 1 — every prime factor of n is ≥ p
--     while every divisor of p-1 is < p, so they share no common factors. Pure
--     minFac structure, independent of the 2^n+1 hypothesis.
-- (b) `min_fac_dvd_three_with_coprime`: given the coprime fact, FLT + the cyclic
--     order argument (orderOf 2 ∣ 2n and ∣ p-1 ⇒ ∣ 2) yields 2² ≡ 1 mod p, hence p ∣ 3.
theorem s9493 : ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → Nat.minFac n ∣ 3  := by
  intro n hn hdvd
  have h_cop := coprime_n_min_fac_pred n hn hdvd
  exact min_fac_dvd_three_with_coprime n hn hdvd h_cop

end Problems.Minif2f.imo_1990_p3
