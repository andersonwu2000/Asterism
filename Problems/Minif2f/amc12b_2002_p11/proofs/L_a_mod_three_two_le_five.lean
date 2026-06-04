import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs

namespace Problems.Minif2f.amc12b_2002_p11

-- a_mod_three_two_le_five: a%3=2 forces 3∣(a-2), so prime a-2=3 pins a=5
-- Since a%3=2 implies (a-2)%3=0, Nat.Prime.eq_one_or_self_of_dvd forces a-2=3, a=5.
theorem a_mod_three_two_le_five : ∀ (a : ℕ) (h₀ : Nat.Prime a)
    (h₂ : Nat.Prime (a + 2)) (h₃ : Nat.Prime (a - 2)),
    a % 3 = 2 → a ≤ 5 := by
  intro a h₀ _h₂ h₃ hmod
  have ha2 : a ≥ 2 := h₀.two_le
  have hdvd3 : 3 ∣ (a - 2) := by
    apply Nat.dvd_of_mod_eq_zero
    omega
  have heq : 3 = 1 ∨ 3 = a - 2 := h₃.eq_one_or_self_of_dvd 3 hdvd3
  rcases heq with h | h <;> omega

end Problems.Minif2f.amc12b_2002_p11
