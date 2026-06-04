import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- coprime_m_div_three_min_fac_pred: any prime r dividing n = m/3 satisfies r ≥ minFac(n),
-- so r cannot also divide minFac(n)-1 < minFac(n); hence gcd(n, minFac(n)-1) = 1.
theorem coprime_m_div_three_min_fac_pred :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      3 ∣ (Nat.minFac (m / 3) - 1) →
      Nat.Coprime (m / 3) (Nat.minFac (m / 3) - 1) := by
  intro m hm _hm2 h3m _h9m _h7m p hp hp5 _hp7 hpm _h3q
  set n := m / 3 with hn_def
  -- m = 3 * n
  have hmul : 3 * n = m := Nat.mul_div_cancel' h3m
  -- p does not divide 3
  have hp_not_dvd_3 : ¬ p ∣ 3 := by
    intro h
    have := Nat.le_of_dvd (by norm_num) h
    omega
  -- p divides n = m/3
  have hpn : p ∣ n := by
    have h : p ∣ 3 * n := hmul ▸ hpm
    exact (hp.dvd_mul.mp h).resolve_left hp_not_dvd_3
  -- n > 0
  have hn_pos : 0 < n := by omega
  -- n ≥ 2
  have hn2 : 2 ≤ n := le_trans hp.two_le (Nat.le_of_dvd hn_pos hpn)
  -- minFac n is prime
  have hq_prime : (n.minFac).Prime := Nat.minFac_prime (by omega)
  -- Coprimality by contradiction
  rw [Nat.Coprime]
  by_contra h
  obtain ⟨r, hr_prime, hr_dvd⟩ := Nat.exists_prime_and_dvd h
  have hr_dvd_n : r ∣ n := dvd_trans hr_dvd (Nat.gcd_dvd_left n (n.minFac - 1))
  have hr_dvd_q1 : r ∣ n.minFac - 1 := dvd_trans hr_dvd (Nat.gcd_dvd_right n (n.minFac - 1))
  have hrq : n.minFac ≤ r := Nat.minFac_le_of_dvd hr_prime.two_le hr_dvd_n
  have hq2 : 2 ≤ n.minFac := hq_prime.two_le
  have hr_lt_q : r ≤ n.minFac - 1 := Nat.le_of_dvd (by omega) hr_dvd_q1
  omega

end Problems.Minif2f.imo_1990_p3
