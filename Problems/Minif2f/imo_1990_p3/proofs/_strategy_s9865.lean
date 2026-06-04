import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_coprime_m_div_three_min_fac_pred

namespace Problems.Minif2f.imo_1990_p3

-- Reduce gcd(q-1, 2m) ∣ 6 to coprimality `(m/3).Coprime (q-1)` where q = Nat.minFac (m/3).
-- Since 2m = 6 * (m/3) and gcd(q-1, m/3) = 1 (smallest-prime-factor argument),
-- `gcd(q-1, 6*(m/3)) = gcd(q-1, 6) ∣ 6`.
theorem s9865 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      3 ∣ (Nat.minFac (m / 3) - 1) →
      Nat.gcd (Nat.minFac (m / 3) - 1) (2*m) ∣ 6  := by
  intro m hm hdvd h3 h9 h7 p hp hpge hp7 hpm h3q
  have hcop := coprime_m_div_three_min_fac_pred m hm hdvd h3 h9 h7 p hp hpge hp7 hpm h3q
  have hm_eq : 2 * m = 6 * (m / 3) := by
    have h := Nat.mul_div_cancel' h3
    omega
  rw [hm_eq]
  calc Nat.gcd (Nat.minFac (m / 3) - 1) (6 * (m / 3))
      = Nat.gcd (6 * (m / 3)) (Nat.minFac (m / 3) - 1) := Nat.gcd_comm _ _
    _ = Nat.gcd 6 (Nat.minFac (m / 3) - 1) := Nat.Coprime.gcd_mul_right_cancel 6 hcop
    _ ∣ 6 := Nat.gcd_dvd_left _ _

end Problems.Minif2f.imo_1990_p3
