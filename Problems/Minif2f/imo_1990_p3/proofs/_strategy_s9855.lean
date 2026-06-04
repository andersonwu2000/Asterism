import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_coprime_m_min_fac_div_three_pred

namespace Problems.Minif2f.imo_1990_p3

-- Strip the gcd against `2*m` by reducing to a coprimality statement.
-- Sub-goal: `Coprime m (q-1)` where q = Nat.minFac (m/3) — purely a number-theoretic
-- claim, no orderOf or ZMod left. Closer: `d := gcd(2m, q-1) ∣ q-1` together with
-- `Coprime m (q-1)` gives `Coprime m d`, and `Coprime d m + d ∣ 2*m` ⇒ `d ∣ 2`.
theorem s9855 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      Nat.gcd (2 * m) (Nat.minFac (m / 3) - 1) ∣ 2  := by
  intro m hm hpow h3 h9 h7 p hp h5 hp7 hpm
  have hcop := coprime_m_min_fac_div_three_pred m hm hpow h3 h9 h7 p hp h5 hp7 hpm
  set d := Nat.gcd (2 * m) (Nat.minFac (m / 3) - 1) with hd_def
  have hd_dvd_2m : d ∣ 2 * m := Nat.gcd_dvd_left _ _
  have hd_dvd_pm1 : d ∣ Nat.minFac (m / 3) - 1 := Nat.gcd_dvd_right _ _
  have hcop_md : Nat.Coprime m d := hcop.coprime_dvd_right hd_dvd_pm1
  exact hcop_md.symm.dvd_of_dvd_mul_right hd_dvd_2m

end Problems.Minif2f.imo_1990_p3
