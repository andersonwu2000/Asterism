import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_eq_three_of_no_nine
import Problems.Minif2f.imo_1990_p3.proofs.L_no_nine_dvd_n

namespace Problems.Minif2f.imo_1990_p3

-- Two-step split (matches parent strategy): (A) LTE bound on v_3(n) shows
-- 9 ∤ n; (B) given the extra hypothesis 9 ∤ n, a smallest-prime-divisor
-- argument on n/3 rules out any prime factor ≥ 5 and forces n = 3.
theorem s9432 : ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → n = 3  := by
  intro n h₀ h₁ h₂
  have h_no_nine := no_nine_dvd_n n h₀ h₁ h₂
  have h_eq_three := eq_three_of_no_nine n h₀ h₁ h₂ h_no_nine
  exact h_eq_three

end Problems.Minif2f.imo_1990_p3
