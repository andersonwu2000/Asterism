import Mathlib
import Problems.Minif2f.aimeI_2000_p7.Defs

namespace Problems.Minif2f.aimeI_2000_p7

-- entry_kind: Builder
theorem y_eq_twenty_four : ∀ (x y z : ℝ) (m : ℚ) (h₀ : 0 < x ∧ 0 < y ∧ 0 < z) (h₁ : x * y * z = 1) (h₂ : x + 1 / z = 5) (h₃ : y + 1 / x = 29) (h₄ : z + 1 / y = m) (h₅ : 0 < m), y = 24 := by grind

end Problems.Minif2f.aimeI_2000_p7
