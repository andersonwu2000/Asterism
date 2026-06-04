import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs

namespace Problems.Minif2f.amc12b_2002_p11

-- a_mod_three_one_le_five: if a%3=1 in a prime triplet then a+2≡0(mod 3) forces a+2=3, so a=1
-- which contradicts Nat.Prime 1, making this case vacuously true.
theorem a_mod_three_one_le_five : ∀ (a : ℕ) (h₀ : Nat.Prime a)
    (h₂ : Nat.Prime (a + 2)) (h₃ : Nat.Prime (a - 2)),
    a % 3 = 1 → a ≤ 5 := by
  intro a h₀ _h₂ _h₃ hmod
  have hmod2 : (a + 2) % 3 = 0 := by omega
  have h3div : 3 ∣ (a + 2) := Nat.dvd_of_mod_eq_zero hmod2
  have ha3 : a + 2 = 3 := by
    have := _h₂.eq_one_or_self_of_dvd 3 h3div
    omega
  have ha1 : a = 1 := by omega
  subst ha1
  exact absurd h₀ (by decide)

end Problems.Minif2f.amc12b_2002_p11
