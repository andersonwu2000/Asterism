import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_five_squared_dvd_n
import Problems.Minif2f.amc12a_2020_p21.proofs.L_pow_three_from_five_squared

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Bootstrap divisibility: lift 5 ∣ n to 5^2 ∣ n via the lcm/gcd equation,
-- then lift 5^2 ∣ n to 5^3 ∣ n via the same identity (gcd_mul_lcm + coprime trick).
-- Each lifting step uses 5!·n = lcm(5!,n)·gcd(5!,n) substituted with `hlcm`,
-- giving 24·n = gcd(10!,n)·gcd(5!,n) and a 5-adic valuation bump.
theorem s9811 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      (5:ℕ)^3 ∣ n  := by
  intro n hyp
  obtain ⟨h5, hlcm⟩ := hyp
  have h_25 : (5:ℕ)^2 ∣ n := five_squared_dvd_n n ⟨h5, hlcm⟩
  exact pow_three_from_five_squared n ⟨h_25, hlcm⟩

end Problems.Minif2f.amc12a_2020_p21
