import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- coprime_m_q_pred_from_not_three: Nat.Coprime m (minFac(m/3)-1) via contradiction on
-- any prime r | gcd(m, q-1): r=3 contradicts hq3; r≠3 gives r | m/3, so
-- minFac(m/3) ≤ r, but r | q-1 < q forces r < minFac(m/3), contradiction.
theorem coprime_m_q_pred_from_not_three :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      ¬ 3 ∣ (Nat.minFac (m / 3) - 1) →
      Nat.Coprime m (Nat.minFac (m / 3) - 1) := by
  intro m hm2 hdvd h3m h9m h7m p hp h5p hp7 hpm hq3
  unfold Nat.Coprime
  by_contra hne
  have hgcd_pos : 0 < Nat.gcd m (Nat.minFac (m / 3) - 1) := by
    apply Nat.pos_of_ne_zero
    simp [Nat.gcd_eq_zero_iff]
    omega
  have hgcd_ne1 : Nat.gcd m (Nat.minFac (m / 3) - 1) ≠ 1 := hne
  obtain ⟨r, hr, hr_dvd_gcd⟩ := Nat.exists_prime_and_dvd hgcd_ne1
  have hr_dvd_m : r ∣ m := hr_dvd_gcd.trans (Nat.gcd_dvd_left m _)
  have hr_dvd_pred : r ∣ (m / 3).minFac - 1 := hr_dvd_gcd.trans (Nat.gcd_dvd_right m _)
  have hm_ge15 : 15 ≤ m := by
    have hp_ne3 : p ≠ 3 := by omega
    have hp3_cop : Nat.Coprime p 3 :=
      (hp.coprime_iff_not_dvd).mpr (fun h =>
        hp_ne3 ((Nat.Prime.eq_one_or_self_of_dvd Nat.prime_three p h).resolve_left
          hp.one_lt.ne'))
    have h3p_dvd : 3 * p ∣ m := hp3_cop.symm.mul_dvd_of_dvd_of_dvd h3m hpm
    have := Nat.le_of_dvd (by omega) h3p_dvd
    linarith
  have hdiv_ge5 : 5 ≤ m / 3 := by
    rw [Nat.le_div_iff_mul_le (by norm_num)]
    omega
  have hq_prime : Nat.Prime (Nat.minFac (m / 3)) := Nat.minFac_prime (by omega)
  have hr_ne3 : r ≠ 3 := fun heq => hq3 (heq ▸ hr_dvd_pred)
  have h3_cop_r : Nat.Coprime 3 r := by
    rw [Nat.coprime_comm, hr.coprime_iff_not_dvd]
    intro h_dvd
    have heq3 : r = 1 ∨ r = 3 := Nat.Prime.eq_one_or_self_of_dvd Nat.prime_three r h_dvd
    exact hr_ne3 (heq3.resolve_left hr.one_lt.ne')
  have hm_eq : 3 * (m / 3) = m := Nat.mul_div_cancel' h3m
  have hr_dvd_div : r ∣ m / 3 := by
    have h3prod : r ∣ 3 * (m / 3) := by rw [hm_eq]; exact hr_dvd_m
    exact h3_cop_r.symm.dvd_of_dvd_mul_left h3prod
  have hminFac_le : Nat.minFac (m / 3) ≤ r :=
    Nat.minFac_le_of_dvd hr.two_le hr_dvd_div
  have hr_le : r ≤ Nat.minFac (m / 3) - 1 := by
    apply Nat.le_of_dvd
    · have : 2 ≤ Nat.minFac (m / 3) := hq_prime.two_le
      omega
    · exact hr_dvd_pred
  omega

end Problems.Minif2f.imo_1990_p3
