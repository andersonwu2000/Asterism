import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- pow_two_m_eq_one: p∣m and m²∣2^m+1 → (2:ZMod p)^(2m)=1 via 2^m≡-1 mod p
-- p∣m∣m²∣2^m+1 gives 2^m=-1 in ZMod p; squaring gives 2^(2m)=1.
theorem pow_two_m_eq_one :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ m → (2 : ZMod p) ^ (2 * m) = 1 := by
  intro m _hm hdvd _h3 _h9 _h7 p _hp _h5 hpm
  have hpdvd : p ∣ 2 ^ m + 1 :=
    dvd_trans (dvd_trans hpm (dvd_pow_self m (by norm_num : 2 ≠ 0))) hdvd
  have hmod : (2 : ZMod p) ^ m + 1 = 0 := by
    have h : ((2 ^ m + 1 : ℕ) : ZMod p) = 0 := by
      rw [CharP.cast_eq_zero_iff (ZMod p) p]
      exact hpdvd
    push_cast at h
    exact h
  have hneg : (2 : ZMod p) ^ m = -1 := by linear_combination hmod
  rw [show 2 * m = m * 2 from mul_comm 2 m, pow_mul, hneg]
  ring

end Problems.Minif2f.imo_1990_p3
