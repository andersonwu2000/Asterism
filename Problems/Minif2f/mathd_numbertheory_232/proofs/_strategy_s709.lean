import Mathlib
import Problems.Minif2f.mathd_numbertheory_232.Defs

namespace Problems.Minif2f.mathd_numbertheory_232

-- Direct: substitute the three equalities and `decide` resolves the
-- concrete computation in `ZMod 31` (3⁻¹ = 21, 5⁻¹ = 25, 15⁻¹ = 29).
theorem s709 : ∀ (x y z : ZMod 31) (h₀ : x = 3⁻¹) (h₁ : y = 5⁻¹) (h₂ : z = (x + y)⁻¹), z = 29  := by
  intro x y z h₀ h₁ h₂
  subst h₀ h₁ h₂
  decide

end Problems.Minif2f.mathd_numbertheory_232
