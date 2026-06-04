import Mathlib
namespace Problems.Minif2f.mathd_numbertheory_709

-- tau_system_solves: (a+2)(b+1)=28 ∧ (a+1)(b+2)=30 uniquely forces a=5,b=3 ⟹ 2^a·3^b=864
-- Bound a ≤ 26 from the first equation, then interval_cases closes both variables.
theorem tau_system_solves :
    ∀ (a b : ℕ),
      (a + 2) * (b + 1) = 28 → (a + 1) * (b + 2) = 30 → 2 ^ a * 3 ^ b = 864 := by
  intro a b h1 h2
  have ha : a = 5 := by
    have ha_bound : a ≤ 26 := by
      have h : a + 2 ≤ 28 := Nat.le_of_dvd (by norm_num) ⟨b + 1, by linarith⟩
      omega
    interval_cases a <;> omega
  have hb : b = 3 := by subst ha; omega
  subst ha; subst hb
  norm_num

end Problems.Minif2f.mathd_numbertheory_709
