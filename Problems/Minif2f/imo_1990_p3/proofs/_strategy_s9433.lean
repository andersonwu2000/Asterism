import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_min_fac_dvd_three
import Problems.Minif2f.imo_1990_p3.proofs.L_min_fac_odd

namespace Problems.Minif2f.imo_1990_p3

-- Reduce `3 ∣ n` to identifying the smallest prime factor of n as 3.
-- (a) `min_fac_dvd_three`: order-of-2 argument forces minFac n to divide 3.
-- (b) `min_fac_odd`: n² ∣ (2^n+1) odd ⇒ n odd ⇒ minFac n > 2.
-- A prime > 2 dividing 3 must equal 3; then `Nat.minFac_dvd` finishes.
theorem s9433 : ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n  := by
  intro n h₀ h₁
  have h_dvd : Nat.minFac n ∣ 3 := min_fac_dvd_three n h₀ h₁
  have h_odd : 2 < Nat.minFac n := min_fac_odd n h₀ h₁
  have h_n_ne_one : n ≠ 1 := by omega
  have h_p_prime : (Nat.minFac n).Prime := Nat.minFac_prime h_n_ne_one
  have h_p_eq : Nat.minFac n = 3 := by
    rcases (Nat.dvd_prime (by norm_num : Nat.Prime 3)).mp h_dvd with h | h
    · omega
    · exact h
  exact h_p_eq ▸ Nat.minFac_dvd n

end Problems.Minif2f.imo_1990_p3
