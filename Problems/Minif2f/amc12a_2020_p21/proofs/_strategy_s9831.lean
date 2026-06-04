import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Direct proof: lift 5²∣n to 5³∣n using gcd_mul_lcm + hlcm.
-- gcd(5!,n)·(5·gcd(10!,n)) = 120·n, then 5|gcd(5!,n), 5²|gcd(10!,n), 5²|n
-- gives 625·a·b = 3000·c → 5·a·b = 24·c → 5∣c → n = 25·c = 125·d.
theorem s9831 :
    ∀ n : ℕ, ((5:ℕ)^2 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      (5:ℕ)^3 ∣ n  := by
  intro n ⟨h5sq, hlcm⟩
  have hprod : Nat.gcd 5! n * (5 * Nat.gcd 10! n) = 120 * n := by
    have h := Nat.gcd_mul_lcm 5! n
    rw [hlcm] at h
    simpa [Nat.factorial] using h
  have h5n : (5 : ℕ) ∣ n := (show (5:ℕ) ∣ 5^2 by norm_num).trans h5sq
  have hgcd5 : (5 : ℕ) ∣ Nat.gcd 5! n := Nat.dvd_gcd (by norm_num) h5n
  have hgcd10 : (5 : ℕ)^2 ∣ Nat.gcd 10! n :=
    Nat.dvd_gcd (by norm_num [Nat.factorial]) h5sq
  obtain ⟨a, ha⟩ := hgcd5
  obtain ⟨b, hb⟩ := hgcd10
  obtain ⟨c, hc⟩ := h5sq
  rw [ha, hb, hc] at hprod
  have hrw : 625 * (a * b) = 3000 * c := by
    have lhs : 5 * a * (5 * (5 ^ 2 * b)) = 625 * (a * b) := by ring
    have rhs : 120 * (5 ^ 2 * c) = 3000 * c := by ring
    linarith
  have h5ab : 5 * (a * b) = 24 * c := by omega
  have h5c : (5 : ℕ) ∣ c :=
    Nat.Coprime.dvd_of_dvd_mul_left (by norm_num : Nat.Coprime 5 24)
      ⟨a * b, by linarith⟩
  obtain ⟨d, hd⟩ := h5c
  exact ⟨d, by rw [hc, hd]; ring⟩

end Problems.Minif2f.amc12a_2020_p21
