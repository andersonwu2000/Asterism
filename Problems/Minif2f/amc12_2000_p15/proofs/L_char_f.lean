import Mathlib
import Problems.Minif2f.amc12_2000_p15.Defs

namespace Problems.Minif2f.amc12_2000_p15

-- char_f: characterize f using substitution x ↦ 3y in h₀
theorem char_f (f : ℂ → ℂ) (h₀ : ∀ x, f (x / 3) = x ^ 2 + x + 1) :
    ∀ y : ℂ, f y = 9 * y^2 + 3 * y + 1 := by
  intro y
  have h := h₀ (3 * y)
  have heq : (3 : ℂ) * y / 3 = y := by ring
  rw [heq] at h
  rw [h]
  ring

end Problems.Minif2f.amc12_2000_p15
