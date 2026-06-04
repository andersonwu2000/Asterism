import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_gcd_two_m_q_pred_dvd_two_kernel

namespace Problems.Minif2f.imo_1990_p3

-- Reduce to the bridging fact `gcd(2m, q-1) ∣ 2` (the orderOf/Fermat-chain conclusion).
-- Closing: 3 ∣ m gives 3 ∣ 2m; if also 3 ∣ q-1, then 3 ∣ gcd(2m, q-1) ∣ 2 — contradiction.
theorem s9857 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      ¬ 3 ∣ (Nat.minFac (m / 3) - 1)  := by
  intro m hm hpow h3 h9 h7 p hp h5 hp7 hpm hq3
  have h_gcd : Nat.gcd (2 * m) (Nat.minFac (m / 3) - 1) ∣ 2 :=
    gcd_two_m_q_pred_dvd_two_kernel m hm hpow h3 h9 h7 p hp h5 hp7 hpm
  have h3_2m : (3 : ℕ) ∣ 2 * m := h3.mul_left 2
  have h3_gcd : (3 : ℕ) ∣ Nat.gcd (2 * m) (Nat.minFac (m / 3) - 1) :=
    Nat.dvd_gcd h3_2m hq3
  exact absurd (h3_gcd.trans h_gcd) (by decide)

end Problems.Minif2f.imo_1990_p3
