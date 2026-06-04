import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- three_lte_upper_base: ¬ 9 ∣ 2^m+1 for odd m with ¬ 3∣m, via ZMod 9 periodicity
-- 9 ∣ 2^m+1 iff m ≡ 3 mod 6 (by ZMod 9 order-6 periodicity of 2),
-- but m ≡ 3 mod 6 implies 3 ∣ m, contradicting the hypothesis.
theorem three_lte_upper_base :
    ∀ (m : ℕ), Odd m → ¬ (3 ∣ m) →
      ¬ 3 ^ (0 + 2) ∣ 2 ^ (3 ^ 0 * m) + 1 := by
  intro m _hm_odd hm_ndvd3 h9dvd
  simp only [pow_zero, one_mul, zero_add] at h9dvd
  -- h9dvd : 3^2 ∣ 2^m + 1, i.e. 9 ∣ 2^m + 1
  have hzmod : (2 : ZMod 9) ^ m + 1 = 0 := by
    have h : ((2 ^ m + 1 : ℕ) : ZMod 9) = 0 :=
      (CharP.cast_eq_zero_iff (ZMod 9) 9 (2 ^ m + 1)).mpr h9dvd
    simpa using h
  -- order of 2 in ZMod 9 is 6
  have hper : (2 : ZMod 9) ^ 6 = 1 := by decide
  -- reduce exponent mod 6
  have hreduce : (2 : ZMod 9) ^ m = (2 : ZMod 9) ^ (m % 6) := by
    conv_lhs => rw [← Nat.div_add_mod m 6]
    rw [pow_add, pow_mul, hper, one_pow, one_mul]
  -- derive the residue constraint
  have hkey : (2 : ZMod 9) ^ (m % 6) + 1 = 0 := by rw [← hreduce]; exact hzmod
  -- case-split on m % 6 ∈ {0,1,2,3,4,5}
  have hlt6 : m % 6 < 6 := Nat.mod_lt m (by norm_num)
  have hcase : m % 6 = 3 := by
    interval_cases (m % 6) <;> simp_all (config := { decide := true })
  -- m % 6 = 3 → m = 3*(2*(m/6)+1) → 3 ∣ m
  exact hm_ndvd3 ⟨2 * (m / 6) + 1, by omega⟩

end Problems.Minif2f.imo_1990_p3
