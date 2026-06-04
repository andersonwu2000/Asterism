import Mathlib
namespace Problems.Minif2f.imo_1990_p3

-- min_fac_div_three_prime_ge_five: Nat.minFac(m/3) is prime ≥ 5
-- via parity (m odd) + ¬9∣m + Nat.Prime.dvd_mul; excludes 2,3,4 by case.
-- 2∤m/3: m²∣2^m+1 forces m odd; 3∤m/3: 3∣(m/3) would give 9∣m, contradicted;
-- 4 not prime; so minFac(m/3) is prime, ≥2, ≠2, ≠3, ≠4, hence ≥5.
theorem min_fac_div_three_prime_ge_five :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      Nat.Prime (Nat.minFac (m / 3)) ∧ 5 ≤ Nat.minFac (m / 3) := by
  intro m hm2 hdvd h3m h9m h7m p hp h5p h7p hpm
  have hm_odd : ¬ (2 ∣ m) := by
    intro h2m
    have h2m2 : 2 ∣ m ^ 2 := dvd_pow h2m (by norm_num)
    have h2_sum : 2 ∣ 2 ^ m + 1 := h2m2.trans hdvd
    have h2_pow : 2 ∣ 2 ^ m := dvd_pow_self 2 (by omega)
    omega
  have h3_div_eq : m = 3 * (m / 3) := by
    have := Nat.div_mul_cancel h3m; omega
  have hpdvd_div : p ∣ m / 3 := by
    have hpdvd3m : p ∣ 3 * (m / 3) := h3_div_eq ▸ hpm
    rcases (hp.dvd_mul).mp hpdvd3m with h | h
    · have := Nat.le_of_dvd (by norm_num) h; omega
    · exact h
  have hdiv_ge : 2 ≤ m / 3 := by
    have hm3 : 3 ≤ m := Nat.le_of_dvd (by omega) h3m
    have hdiv_pos : 0 < m / 3 := Nat.div_pos hm3 (by norm_num)
    have hple : p ≤ m / 3 := Nat.le_of_dvd hdiv_pos hpdvd_div
    omega
  constructor
  · exact Nat.minFac_prime (by omega)
  · have hminFac_prime : Nat.Prime (Nat.minFac (m / 3)) := Nat.minFac_prime (by omega)
    have hminFac_dvd : Nat.minFac (m / 3) ∣ m / 3 := Nat.minFac_dvd _
    have hne2 : Nat.minFac (m / 3) ≠ 2 := by
      intro heq
      have h2div : 2 ∣ m / 3 := by have := hminFac_dvd; rw [heq] at this; exact this
      have h2m : 2 ∣ m := by rw [h3_div_eq]; exact h2div.mul_left 3
      exact hm_odd h2m
    have hne3 : Nat.minFac (m / 3) ≠ 3 := by
      intro heq
      apply h9m
      have h3dvd_div : 3 ∣ m / 3 := by have := hminFac_dvd; rw [heq] at this; exact this
      have h9 : 3 * 3 ∣ 3 * (m / 3) := Nat.mul_dvd_mul_left 3 h3dvd_div
      rwa [← h3_div_eq] at h9
    have hne4 : Nat.minFac (m / 3) ≠ 4 := by
      intro h; rw [h] at hminFac_prime; exact absurd hminFac_prime (by decide)
    have hge2 := hminFac_prime.two_le
    omega

end Problems.Minif2f.imo_1990_p3
