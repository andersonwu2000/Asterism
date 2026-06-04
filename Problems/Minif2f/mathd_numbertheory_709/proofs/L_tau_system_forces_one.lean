import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs

namespace Problems.Minif2f.mathd_numbertheory_709

-- tau_system_forces_one: t | gcd(28,30)=2 forces t∈{1,2}; t=2 ruled out by
-- interval_cases a, b (checking (a+2)(b+1)=14 vs (a+1)(b+2)=15 has no ℕ solution)
theorem tau_system_forces_one :
    ∀ (a b t : ℕ),
      (a + 2) * (b + 1) * t = 28 → (a + 1) * (b + 2) * t = 30 → t = 1 := by
  intro a b t h1 h2
  have ht_pos : 0 < t := by
    rcases Nat.eq_zero_or_pos t with rfl | h
    · simp at h1
    · exact h
  have ht_dvd28 : t ∣ 28 := ⟨(a + 2) * (b + 1), by nlinarith⟩
  have ht_dvd30 : t ∣ 30 := ⟨(a + 1) * (b + 2), by nlinarith⟩
  have ht_dvd2 : t ∣ 2 := by
    have hg := Nat.dvd_gcd ht_dvd28 ht_dvd30
    norm_num at hg
    exact hg
  have htle : t ≤ 2 := Nat.le_of_dvd (by norm_num) ht_dvd2
  interval_cases t
  · rfl
  · -- t = 2: (a+2)(b+1) = 14 and (a+1)(b+2) = 15, impossible
    have ha_le : a ≤ 12 := by nlinarith [show 0 < b + 1 from by omega]
    have hb_le : b ≤ 6 := by nlinarith [show 2 ≤ a + 2 from by omega]
    interval_cases a <;> interval_cases b <;> omega

end Problems.Minif2f.mathd_numbertheory_709
