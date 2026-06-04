import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_coprime_m_p_sub_one

namespace Problems.Minif2f.imo_1990_p3

-- Reduce gcd(2m, p-1) ∣ 2 to Coprime m (p-1):
-- given Coprime m (p-1), every divisor d of p-1 is coprime to m;
-- since d := gcd(2m, p-1) divides p-1, Coprime m d holds, and
-- d ∣ 2*m with Coprime d m yields d ∣ 2 via dvd_of_dvd_mul_right.
theorem s9843 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ m → Nat.gcd (2 * m) (p - 1) ∣ 2  := by
  intro m hm hpow h3 h9 h7 p hp h5 hpm
  have hcop : Nat.Coprime m (p - 1) :=
    coprime_m_p_sub_one m hm hpow h3 h9 h7 p hp h5 hpm
  have hd_2m : Nat.gcd (2 * m) (p - 1) ∣ 2 * m := Nat.gcd_dvd_left _ _
  have hd_pm1 : Nat.gcd (2 * m) (p - 1) ∣ p - 1 := Nat.gcd_dvd_right _ _
  have hcop_md : Nat.Coprime m (Nat.gcd (2 * m) (p - 1)) := hcop.coprime_dvd_right hd_pm1
  exact hcop_md.symm.dvd_of_dvd_mul_right hd_2m

end Problems.Minif2f.imo_1990_p3
