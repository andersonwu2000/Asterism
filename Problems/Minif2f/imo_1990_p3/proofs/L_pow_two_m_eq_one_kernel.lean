import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- pow_two_m_eq_one_kernel: from m²∣2^m+1 and q=minFac(m/3)∣m, get (2:ZMod q)^(2m)=1 via 2^m≡-1
theorem pow_two_m_eq_one_kernel :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      3 ∣ (Nat.minFac (m / 3) - 1) →
      (2 : ZMod (Nat.minFac (m / 3)))^(2*m) = 1 := by
  intro m _hm hdvd h3m _h9m _h7m _p _hp _h5p _hp7 _hpm _hq3
  set q := Nat.minFac (m / 3) with _hq_def
  have hq_dvd_m3 : q ∣ m / 3 := Nat.minFac_dvd (m / 3)
  have hm3_dvd_m : m / 3 ∣ m := Nat.div_dvd_of_dvd h3m
  have hq_dvd_m : q ∣ m := hq_dvd_m3.trans hm3_dvd_m
  have hq2_dvd_m2 : q ^ 2 ∣ m ^ 2 := by
    rw [sq, sq]; exact Nat.mul_dvd_mul hq_dvd_m hq_dvd_m
  have hq2_dvd : q ^ 2 ∣ 2 ^ m + 1 := hq2_dvd_m2.trans hdvd
  have hq_dvd : q ∣ 2 ^ m + 1 := (dvd_pow_self q (by norm_num : 2 ≠ 0)).trans hq2_dvd
  have hsum : (2 : ZMod q) ^ m + 1 = 0 := by
    have hcast : ((2 ^ m + 1 : ℕ) : ZMod q) = 0 := by
      rw [CharP.cast_eq_zero_iff (ZMod q) q]
      exact hq_dvd
    simpa using hcast
  have h2m_neg : (2 : ZMod q) ^ m = -1 := by linear_combination hsum
  rw [show 2 * m = m * 2 from by ring, pow_mul, h2m_neg]
  ring

end Problems.Minif2f.imo_1990_p3
