import Mathlib
import Problems.Minif2f.mathd_numbertheory_110.Defs

namespace Problems.Minif2f.mathd_numbertheory_110

-- Direct: omega handles modular arithmetic with b ≤ a (Nat sub is exact here).
theorem s520 : ∀ (a b : ℕ) (h₀ : 0 < a ∧ 0 < b ∧ b ≤ a) (h₁ : (a + b) % 10 = 2) (h₂ : (2 * a + b) % 10 = 1), (a - b) % 10 = 6  := by
  intro a b h₀ h₁ h₂
  obtain ⟨ha, hb, hab⟩ := h₀
  omega

end Problems.Minif2f.mathd_numbertheory_110
