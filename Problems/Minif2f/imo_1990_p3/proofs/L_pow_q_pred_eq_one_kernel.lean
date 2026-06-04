import Mathlib
namespace Problems.Minif2f.imo_1990_p3

-- pow_q_pred_eq_one_kernel: Fermat's little theorem closes 2^(q-1)=1 in ZMod q,
-- where q=minFac(m/3) is prime ≥ 5 (forced by p≥5, p∣m, 3∣m) and 2≠0 since 3∣(q-1)⟹q≠2.
theorem pow_q_pred_eq_one_kernel :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      3 ∣ (Nat.minFac (m / 3) - 1) →
      (2 : ZMod (Nat.minFac (m / 3)))^(Nat.minFac (m / 3) - 1) = 1 := by
    intro m hm2 hdvd_m2 hdvd3 hno9 hno7 p hp hpge _hpne7 hpm hdvd3q
    have h3p_dvd : 3 * p ∣ m := by
      apply Nat.Coprime.mul_dvd_of_dvd_of_dvd
      · rw [Nat.coprime_comm]
        apply hp.coprime_iff_not_dvd.mpr
        intro hpdvd3
        have := Nat.le_of_dvd (by norm_num) hpdvd3
        linarith
      · exact hdvd3
      · exact hpm
    have hm_lb : 15 ≤ m := by
      calc 15 = 3 * 5 := by norm_num
        _ ≤ 3 * p := Nat.mul_le_mul_left 3 hpge
        _ ≤ m := Nat.le_of_dvd (by linarith) h3p_dvd
    have hm3_ge5 : 5 ≤ m / 3 := by
      obtain ⟨k, hk⟩ := hdvd3
      rw [hk, Nat.mul_div_cancel_left _ (by norm_num : 0 < 3)]
      have : 15 ≤ 3 * k := hk ▸ hm_lb
      omega
    have hm3_ne1 : m / 3 ≠ 1 := by omega
    have hq_prime : (Nat.minFac (m / 3)).Prime := Nat.minFac_prime hm3_ne1
    have hq_ne2 : Nat.minFac (m / 3) ≠ 2 := by
      intro heq
      rw [heq] at hdvd3q
      norm_num at hdvd3q
    have h2_ne0 : (2 : ZMod (Nat.minFac (m / 3))) ≠ 0 := by
      haveI : Fact (Nat.minFac (m / 3)).Prime := ⟨hq_prime⟩
      intro h
      rw [show (2 : ZMod (Nat.minFac (m / 3))) = ((2 : ℕ) : ZMod (Nat.minFac (m / 3)))
          from by norm_cast] at h
      rw [CharP.cast_eq_zero_iff (ZMod (Nat.minFac (m / 3))) (Nat.minFac (m / 3))] at h
      have hqge3 : 3 ≤ Nat.minFac (m / 3) := by
        have := hq_prime.two_le; omega
      linarith [Nat.le_of_dvd (by norm_num) h]
    haveI : Fact (Nat.minFac (m / 3)).Prime := ⟨hq_prime⟩
    exact ZMod.pow_card_sub_one_eq_one h2_ne0

end Problems.Minif2f.imo_1990_p3
