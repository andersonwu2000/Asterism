import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_nine_not_dvd_of_odd
import Problems.Minif2f.imo_1990_p3.proofs.L_n_is_odd

namespace Problems.Minif2f.imo_1990_p3

-- Two-step split aligned with parent strategy (LTE bound on v_3):
-- (1) `n_is_odd`: n²∣(2^n+1) forces n odd (since 2^n+1 is odd).
-- (2) `nine_not_dvd_of_odd`: with Odd n in hand, the LTE identity
--     v_3(2^n+1) = 1 + v_3(n) combined with n²∣(2^n+1) gives v_3(n) ≤ 1,
--     ruling out 9 ∣ n.
theorem s9490 :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → ¬ (9 ∣ n)  := by
  intro n h₀ h₁ h₃
  have h_odd : Odd n := n_is_odd n h₀ h₁
  exact nine_not_dvd_of_odd n h₀ h_odd h₁ h₃

end Problems.Minif2f.imo_1990_p3
