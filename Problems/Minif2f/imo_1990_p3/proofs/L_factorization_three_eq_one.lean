import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- factorization_three_eq_one: 3∣m and ¬9∣m bound v₃(m) to exactly 1 via
-- Nat.Prime.pow_dvd_iff_le_factorization applied at k=1 and k=2
theorem factorization_three_eq_one :
    ∀ (m : ℕ), 2 ≤ m → Odd m → 3 ∣ m → ¬ (9 ∣ m) →
      (∀ p, Nat.Prime p → 5 ≤ p → ¬ p ∣ m) →
      m.factorization 3 = 1 := by
  intro m hm2 _hodd h3 h9 _hno
  have hm_ne : m ≠ 0 := by omega
  have h_ge1 : 1 ≤ m.factorization 3 := by
    rw [← Nat.Prime.pow_dvd_iff_le_factorization Nat.prime_three hm_ne]
    simpa using h3
  have h_lt2 : m.factorization 3 < 2 := by
    by_contra h
    push Not at h
    apply h9
    rw [show (9 : ℕ) = 3 ^ 2 by norm_num]
    rwa [Nat.Prime.pow_dvd_iff_le_factorization Nat.prime_three hm_ne]
  omega

end Problems.Minif2f.imo_1990_p3
