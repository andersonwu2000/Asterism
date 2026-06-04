import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_eq_three_of_three_dvd
import Problems.Minif2f.imo_1990_p3.proofs.L_three_dvd_n

namespace Problems.Minif2f.imo_1990_p3

-- Classical IMO 1990 P3 outline: split into (a) force 3 ∣ n via smallest-prime-
-- divisor / multiplicative-order argument, (b) upgrade 3 ∣ n to n = 3 via
-- lifting-the-exponent + a second smallest-prime-divisor contradiction on n/3.
theorem s9295 : ∀ (n : ℕ) (h₀ : 2 ≤ n) (h₁ : n ^ 2 ∣ 2 ^ n + 1), n = 3  := by
  intro n h₀ h₁
  have h_three_dvd_n := three_dvd_n n h₀ h₁
  have h_eq_three_of_three_dvd := eq_three_of_three_dvd n h₀ h₁ h_three_dvd_n
  exact h_eq_three_of_three_dvd

end Problems.Minif2f.imo_1990_p3
