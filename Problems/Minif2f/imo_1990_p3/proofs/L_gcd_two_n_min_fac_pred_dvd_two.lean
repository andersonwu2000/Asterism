import Mathlib
namespace Problems.Minif2f.imo_1990_p3

-- gcd_two_n_min_fac_pred_dvd_two: gcd(2n, p-1) ∣ 2 follows from Coprime n (p-1) via
-- d ∣ p-1 and Coprime n (p-1) ⇒ Coprime n d ⇒ d ∣ 2*n ∧ Coprime d n ⇒ d ∣ 2
theorem gcd_two_n_min_fac_pred_dvd_two :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 →
      Nat.Coprime n (Nat.minFac n - 1) →
      Nat.gcd (2*n) (Nat.minFac n - 1) ∣ 2 := by
  intro n _hn _hpow hcop
  set d := Nat.gcd (2 * n) (Nat.minFac n - 1) with hd_def
  have hd_dvd_2n : d ∣ 2 * n := Nat.gcd_dvd_left _ _
  have hd_dvd_pm1 : d ∣ Nat.minFac n - 1 := Nat.gcd_dvd_right _ _
  have hcop_nd : Nat.Coprime n d := hcop.coprime_dvd_right hd_dvd_pm1
  exact hcop_nd.symm.dvd_of_dvd_mul_right hd_dvd_2n

end Problems.Minif2f.imo_1990_p3
