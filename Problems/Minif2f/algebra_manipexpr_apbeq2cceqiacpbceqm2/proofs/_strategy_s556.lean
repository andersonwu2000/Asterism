import Mathlib
import Problems.Minif2f.algebra_manipexpr_apbeq2cceqiacpbceqm2.Defs

namespace Problems.Minif2f.algebra_manipexpr_apbeq2cceqiacpbceqm2

-- Direct: a*c + b*c = (a+b)*c = 2c² = 2·I² = -2.
-- `linear_combination I * h₀ + 2 * Complex.I_sq` discharges the ring identity.
theorem s556 : ∀ (a b c : ℂ) (h₀ : a + b = 2 * c) (h₁ : c = Complex.I), a * c + b * c = -2  := by
  intro a b c h₀ h₁
  subst h₁
  linear_combination Complex.I * h₀ + 2 * Complex.I_sq

end Problems.Minif2f.algebra_manipexpr_apbeq2cceqiacpbceqm2
