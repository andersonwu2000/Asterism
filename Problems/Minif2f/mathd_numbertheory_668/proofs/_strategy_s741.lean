import Mathlib
import Problems.Minif2f.mathd_numbertheory_668.Defs

namespace Problems.Minif2f.mathd_numbertheory_668

-- Direct leaf proof: substitute both hypotheses and decide on the finite ZMod 7 equation.
theorem s741 : ∀ (l r : ZMod 7) (h₀ : l = (2 + 3)⁻¹) (h₁ : r = 2⁻¹ + 3⁻¹), l - r = 1  := by
  intro l r h₀ h₁
  subst h₀ h₁
  decide

end Problems.Minif2f.mathd_numbertheory_668
