import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_coprime_m_min_fac_div_three_pred_2

namespace Problems.Minif2f.imo_1990_p3

-- Reduce to `Coprime m (minFac (m/3) - 1)` (the bridging coprimality from
-- the orderOf/Fermat chain). Then d := gcd(2m, q-1) divides 2m and q-1, so
-- coprime_dvd_right gives Coprime m d, and `Nat.Coprime.dvd_of_dvd_mul_right`
-- collapses d ∣ 2m to d ∣ 2.
theorem s9858 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      Nat.gcd (2 * m) (Nat.minFac (m / 3) - 1) ∣ 2  := by
  intro m hm hpow h3 h9 h7 p hp h5 hp7 hpm
  have hcop : Nat.Coprime m (Nat.minFac (m / 3) - 1) :=
    coprime_m_min_fac_div_three_pred_2 m hm hpow h3 h9 h7 p hp h5 hp7 hpm
  set d := Nat.gcd (2 * m) (Nat.minFac (m / 3) - 1) with hd_def
  have hd_dvd_2m : d ∣ 2 * m := Nat.gcd_dvd_left _ _
  have hd_dvd_pm1 : d ∣ Nat.minFac (m / 3) - 1 := Nat.gcd_dvd_right _ _
  have hcop_md : Nat.Coprime m d := hcop.coprime_dvd_right hd_dvd_pm1
  exact hcop_md.symm.dvd_of_dvd_mul_right hd_dvd_2m

end Problems.Minif2f.imo_1990_p3
