import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs
import Problems.Minif2f.amc12b_2002_p11.proofs.L_a_eq_five_when_b_two
import Problems.Minif2f.amc12b_2002_p11.proofs.L_b_eq_two

namespace Problems.Minif2f.amc12b_2002_p11

-- Decompose into (1) parity argument forcing b = 2, and (2) prime-triplet
-- argument forcing a = 5 once b = 2 is known.
-- After substituting b = 2, the original parameters Nat.Prime (a + b) and
-- Nat.Prime (a - b) become Nat.Prime (a + 2) and Nat.Prime (a - 2), which
-- exactly match the hypotheses of the second sub-goal.
theorem s9326 : ∀ (a b : ℕ) (h₀ : Nat.Prime a) (h₁ : Nat.Prime b)
    (h₂ : Nat.Prime (a + b)) (h₃ : Nat.Prime (a - b)), a = 5  := by
  intro a b h₀ h₁ h₂ h₃
  have hb : b = 2 := b_eq_two a b h₀ h₁ h₂ h₃
  subst hb
  exact a_eq_five_when_b_two a h₀ h₂ h₃

end Problems.Minif2f.amc12b_2002_p11
