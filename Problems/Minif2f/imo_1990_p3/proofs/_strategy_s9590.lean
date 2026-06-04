import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_eq_three_of_no_large_prime
import Problems.Minif2f.imo_1990_p3.proofs.L_no_prime_ge_five_dvd

namespace Problems.Minif2f.imo_1990_p3

-- Two-step smallest-prime-factor split under the extra hypothesis `¬ 9 ∣ n`.
-- (A) `no_prime_ge_five_dvd`: hypotheses rule out any prime ≥ 5 dividing `n`
--     (order-of-2 mod p contradicts n² ∣ 2ⁿ+1).
-- (B) `eq_three_of_no_large_prime`: with no large prime + 3 ∣ n + ¬ 9 ∣ n,
--     `min_fac`-style oddness + n = 3^k arithmetic forces n = 3.
theorem s9590 :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → ¬ (9 ∣ n) → n = 3  := by
  intro n h₀ h₁ h₂ h₃
  have h_no_large := no_prime_ge_five_dvd n h₀ h₁ h₂ h₃
  exact eq_three_of_no_large_prime n h₀ h₁ h₂ h₃ h_no_large

end Problems.Minif2f.imo_1990_p3
