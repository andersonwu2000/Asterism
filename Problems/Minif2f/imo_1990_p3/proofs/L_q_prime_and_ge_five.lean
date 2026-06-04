import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- q_prime_and_ge_five: minFac(m/3) is prime ≥ 5 given a prime p≥5, p≠7 dividing m
theorem q_prime_and_ge_five :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      Nat.Prime (Nat.minFac (m / 3)) ∧ 5 ≤ Nat.minFac (m / 3) := by
  intro m hm hdvd h3 h9 h7 p hp hpge hp7 hpm
  have hm_eq : 3 * (m / 3) = m := Nat.mul_div_cancel' h3
  -- p is coprime to 3 (p ≥ 5, so p ∤ 3)
  have hp_not3 : ¬ p ∣ 3 := fun h => absurd (Nat.le_of_dvd (by decide) h) (by omega)
  have hcop : Nat.Coprime p 3 := hp.coprime_iff_not_dvd.mpr hp_not3
  -- p ∣ m/3
  have hpdvd_k : p ∣ m / 3 := by
    have h : p ∣ 3 * (m / 3) := by rwa [hm_eq]
    exact hcop.dvd_of_dvd_mul_left h
  -- m/3 ≥ 2
  have hm3_le : 3 ≤ m := Nat.le_of_dvd (by omega) h3
  have hk_pos : 0 < m / 3 := Nat.div_pos hm3_le (by decide)
  have hk_ge2 : 2 ≤ m / 3 := by
    have := Nat.le_of_dvd hk_pos hpdvd_k
    omega
  -- minFac(m/3) is prime
  have hq_prime : Nat.Prime (Nat.minFac (m / 3)) := Nat.minFac_prime (by omega)
  have hq_dvd : Nat.minFac (m / 3) ∣ m / 3 := Nat.minFac_dvd _
  -- 2 ∤ m/3
  have h_odd_2m1 : ¬ 2 ∣ (2 ^ m + 1) := by
    intro h
    obtain ⟨k, hk⟩ := h
    have h2_dvd_pow : 2 ∣ 2 ^ m := dvd_pow_self 2 (by omega)
    obtain ⟨j, hj⟩ := h2_dvd_pow
    omega
  have h_odd_m : ¬ 2 ∣ m := by
    intro h
    apply h_odd_2m1
    exact (dvd_pow h (by omega)).trans hdvd
  have h_odd_k : ¬ 2 ∣ (m / 3) := by
    intro h
    apply h_odd_m
    have : 2 ∣ 3 * (m / 3) := h.mul_left 3
    rwa [hm_eq] at this
  -- 3 ∤ m/3
  have h_not3_k : ¬ 3 ∣ (m / 3) := by
    intro h
    apply h9
    have : 3 * 3 ∣ 3 * (m / 3) := Nat.mul_dvd_mul_left 3 h
    rwa [show 3 * 3 = 9 from rfl, hm_eq] at this
  -- minFac(m/3) ≠ 2
  have hq_ne2 : Nat.minFac (m / 3) ≠ 2 := fun h => h_odd_k (h ▸ hq_dvd)
  -- minFac(m/3) ≠ 3
  have hq_ne3 : Nat.minFac (m / 3) ≠ 3 := by
    intro h
    apply h_not3_k
    have hq_dvd' := hq_dvd
    rw [h] at hq_dvd'
    exact hq_dvd'
  -- minFac(m/3) is odd (prime ≠ 2) → ≥ 5
  have hq_odd : Nat.minFac (m / 3) % 2 = 1 := by
    have := hq_prime.eq_two_or_odd
    omega
  have hq_ge2 : 2 ≤ Nat.minFac (m / 3) := hq_prime.two_le
  have hq_ge5 : 5 ≤ Nat.minFac (m / 3) := by omega
  exact ⟨hq_prime, hq_ge5⟩

end Problems.Minif2f.imo_1990_p3
