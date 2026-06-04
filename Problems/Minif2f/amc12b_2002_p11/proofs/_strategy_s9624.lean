import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs
import Problems.Minif2f.amc12b_2002_p11.proofs.L_a_mod_three_one_le_five
import Problems.Minif2f.amc12b_2002_p11.proofs.L_a_mod_three_two_le_five
import Problems.Minif2f.amc12b_2002_p11.proofs.L_a_mod_three_zero_le_five

namespace Problems.Minif2f.amc12b_2002_p11

-- Case split on a % 3: in any prime triplet {a-2, a, a+2}, exactly one of
-- the three values is ≡ 0 (mod 3). Each residue class delegates to a sub-goal
-- that uses the corresponding prime hypothesis to bound a ≤ 5.
theorem s9624 : ∀ (a : ℕ) (h₀ : Nat.Prime a)
    (h₂ : Nat.Prime (a + 2)) (h₃ : Nat.Prime (a - 2)), a ≤ 5  := by
  intro a h₀ h₂ h₃
  have h_zero := a_mod_three_zero_le_five a h₀ h₂ h₃
  have h_one := a_mod_three_one_le_five a h₀ h₂ h₃
  have h_two := a_mod_three_two_le_five a h₀ h₂ h₃
  have hmod : a % 3 = 0 ∨ a % 3 = 1 ∨ a % 3 = 2 := by omega
  rcases hmod with h | h | h
  · exact h_zero h
  · exact h_one h
  · exact h_two h

end Problems.Minif2f.amc12b_2002_p11
