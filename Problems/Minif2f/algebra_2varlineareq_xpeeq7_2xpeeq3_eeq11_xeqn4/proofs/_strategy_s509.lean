import Mathlib
import Problems.Minif2f.algebra_2varlineareq_xpeeq7_2xpeeq3_eeq11_xeqn4.Defs

namespace Problems.Minif2f.algebra_2varlineareq_xpeeq7_2xpeeq3_eeq11_xeqn4

-- Direct closed-form: 2·h₀ − h₁ gives e = 11; h₁ − h₀ gives x = -4.
-- Linear system in ℂ closed by `linear_combination`, no sub-goals needed.
theorem s509 : ∀ (x e : ℂ) (h₀ : x + e = 7) (h₁ : 2 * x + e = 3), e = 11 ∧ x = -4  := by
  intro x e h₀ h₁
  refine ⟨?_, ?_⟩
  · linear_combination 2 * h₀ - h₁
  · linear_combination h₁ - h₀

end Problems.Minif2f.algebra_2varlineareq_xpeeq7_2xpeeq3_eeq11_xeqn4
