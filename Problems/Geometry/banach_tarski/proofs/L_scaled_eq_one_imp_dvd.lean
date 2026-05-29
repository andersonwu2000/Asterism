import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- scaled_eq_one_imp_dvd: from 1 = (1/3)^n * q with n ≥ 1, derive 3 ∣ q via q = 3^n over ℤ
theorem scaled_eq_one_imp_dvd
    (n : ℕ) (q : ℤ) (hn : 1 ≤ n)
    (h : (1 : ℝ) = ((1 : ℝ) / 3) ^ n * (q : ℝ)) :
    (3 : ℤ) ∣ q := by
  have hq : (q : ℝ) = 3 ^ n := by
    have h3ne : (3 : ℝ) ^ n ≠ 0 := by positivity
    rw [one_div, inv_pow] at h
    field_simp [h3ne] at h
    linarith
  have hqZ : q = 3 ^ n := by exact_mod_cast hq
  rw [hqZ]
  exact dvd_pow_self 3 (by omega)

end Problems.Geometry.banach_tarski
