import Mathlib
namespace Problems.Minif2f.imo_1990_p3

-- seven_not_dvd_n_of_sq: 7 ∤ m via: 7 ∣ m → 7 ∣ m² ∣ 2^m+1, but ord₇(2)=3
-- so 2^m mod 7 ∈ {1,2,4}, making 2^m+1 ∈ {2,3,5} mod 7 — never 0.
theorem seven_not_dvd_n_of_sq :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → ¬ (7 ∣ m) := by
  intro m _hm hdvd h7
  have h7sq : (7 : ℕ) ∣ m ^ 2 := dvd_pow h7 (by norm_num)
  have h7_2m1 : (7 : ℕ) ∣ 2 ^ m + 1 := h7sq.trans hdvd
  have hmod : ((2 ^ m + 1 : ℕ) : ZMod 7) = 0 :=
    (CharP.cast_eq_zero_iff (ZMod 7) 7 _).mpr h7_2m1
  push_cast at hmod
  have hper : (2 : ZMod 7) ^ 3 = 1 := by decide
  have hmod3 : (2 : ZMod 7) ^ m = (2 : ZMod 7) ^ (m % 3) := by
    conv_lhs => rw [← Nat.div_add_mod m 3]
    rw [pow_add, pow_mul, hper, one_pow, one_mul]
  rw [hmod3] at hmod
  have hlt : m % 3 < 3 := Nat.mod_lt m (by norm_num)
  interval_cases (m % 3) <;> simp_all (config := { decide := true })

end Problems.Minif2f.imo_1990_p3
