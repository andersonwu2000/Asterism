import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_m_eq_three_given_hypotheses

namespace Problems.Minif2f.imo_1990_p3

-- Vacuity reduction: the hypotheses (m ≥ 2, m²∣2^m+1, 3∣m, ¬9∣m, ¬7∣m)
-- force m = 3 (IMO 1990 P3 conclusion); under m = 3 no prime p ≥ 5 can
-- divide m, so the ∀ p body — including the gcd equality — is vacuous.
-- One sub-goal: `m_eq_three_given_hypotheses` (the IMO conclusion).
theorem s9846 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ m → Nat.gcd (2 * m) (p - 1) = 2  := by
  intro m hm hpow h3 h9 h7 p hp h5 hpm
  have hm3 : m = 3 := m_eq_three_given_hypotheses m hm hpow h3 h9 h7
  exfalso
  rw [hm3] at hpm
  have hpa : p ≤ 3 := Nat.le_of_dvd (by norm_num) hpm
  omega

end Problems.Minif2f.imo_1990_p3
