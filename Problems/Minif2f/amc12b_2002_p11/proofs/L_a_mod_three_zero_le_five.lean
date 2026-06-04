import Mathlib
namespace Problems.Minif2f.amc12b_2002_p11

-- a_mod_three_zero_le_five: if a, a+2, a-2 prime and a % 3 = 0, then a = 3
-- (Nat.Prime + 3 ∣ a forces a = 3; then h₃ : Nat.Prime 1 is false — contradiction)
theorem a_mod_three_zero_le_five : ∀ (a : ℕ) (h₀ : Nat.Prime a)
    (h₂ : Nat.Prime (a + 2)) (h₃ : Nat.Prime (a - 2)),
    a % 3 = 0 → a ≤ 5 := by
  intro a h₀ h₂ h₃ ha3
  have h3a : 3 ∣ a := Nat.dvd_of_mod_eq_zero ha3
  have heq : a = 3 := by
    have := h₀.eq_one_or_self_of_dvd 3 h3a
    omega
  subst heq
  norm_num at h₃

end Problems.Minif2f.amc12b_2002_p11
