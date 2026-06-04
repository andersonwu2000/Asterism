import Mathlib
namespace Problems.Minif2f.amc12a_2020_p21

open Nat

-- five_squared_dvd_n: 5^2 ∣ n via gcd*lcm=5!*n identity + 5-adic valuation bump.
-- Substituting lcm(5!,n)=5*gcd(10!,n) gives gcd(5!,n)*gcd(10!,n)=24*n;
-- since 5 ∣ both gcds, 25 ∣ 24*n, and Coprime 25 24 yields 25 ∣ n.
theorem five_squared_dvd_n :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      (5:ℕ)^2 ∣ n := by
  intro n ⟨h5, hlcm⟩
  have hprod : Nat.gcd 5! n * (5 * Nat.gcd 10! n) = 120 * n := by
    have h := Nat.gcd_mul_lcm 5! n
    rw [hlcm] at h
    simpa [Nat.factorial] using h
  have hgcd5 : (5 : ℕ) ∣ Nat.gcd 5! n := Nat.dvd_gcd (by norm_num) h5
  have hgcd10 : (5 : ℕ) ∣ Nat.gcd 10! n := Nat.dvd_gcd (by norm_num) h5
  obtain ⟨a, ha⟩ := hgcd5
  obtain ⟨b, hb⟩ := hgcd10
  obtain ⟨c, hc⟩ := h5
  rw [ha, hb, hc] at hprod
  have h25_24n : (25 : ℕ) ∣ 24 * n := ⟨a * b, by rw [hc]; linarith⟩
  have h25n : (25 : ℕ) ∣ n :=
    (Nat.Coprime.dvd_of_dvd_mul_left (by norm_num : Nat.Coprime 25 24) h25_24n)
  rw [show (5 : ℕ)^2 = 25 from by norm_num]
  exact h25n

end Problems.Minif2f.amc12a_2020_p21
