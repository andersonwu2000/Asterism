import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs
import Problems.Minif2f.imo_1977_p5.proofs.L_ab_pair

namespace Problems.Minif2f.imo_1977_p5

-- Reduce to the underlying ℕ-equality form {a,b} = {37,50}; the abs/coercion
-- arithmetic is then trivially decidable by case-splitting on which root each
-- variable takes.
theorem s612 : ∀ (a b q r : ℕ) (h₀ : r < a + b) (h₁ : a ^ 2 + b ^ 2 = (a + b) * q + r) (h₂ : q ^ 2 + r = 1977), abs ((a : ℤ) - 22) = 15 ∧ abs ((b : ℤ) - 22) = 28 ∨ abs ((a : ℤ) - 22) = 28 ∧ abs ((b : ℤ) - 22) = 15  := by
  intro a b q r h₀ h₁ h₂
  have h_ab := ab_pair a b q r h₀ h₁ h₂
  rcases h_ab with ⟨ha, hb⟩ | ⟨ha, hb⟩
  · left
    refine ⟨?_, ?_⟩
    · subst ha; decide
    · subst hb; decide
  · right
    refine ⟨?_, ?_⟩
    · subst ha; decide
    · subst hb; decide

end Problems.Minif2f.imo_1977_p5
