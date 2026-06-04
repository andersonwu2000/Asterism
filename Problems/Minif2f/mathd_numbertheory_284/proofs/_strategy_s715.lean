import Mathlib
import Problems.Minif2f.mathd_numbertheory_284.Defs

namespace Problems.Minif2f.mathd_numbertheory_284

-- Direct linear-arithmetic closure: from h₁ (10a + b = 2(a + b)) we get 8a = b;
-- combined with 1 ≤ a and b ≤ 9 the only solution is a = 1, b = 8, so 10a + b = 18.
-- `omega` handles this bounded linear-Diophantine reasoning in one step after destructuring h₀.
theorem s715 : ∀ (a b : ℕ) (h₀ : 1 ≤ a ∧ a ≤ 9 ∧ b ≤ 9) (h₁ : 10 * a + b = 2 * (a + b)), 10 * a + b = 18  := by
  intro a b h₀ h₁
  obtain ⟨ha₁, ha₂, hb⟩ := h₀
  omega

end Problems.Minif2f.mathd_numbertheory_284
