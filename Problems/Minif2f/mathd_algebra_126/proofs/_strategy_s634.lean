import Mathlib
import Problems.Minif2f.mathd_algebra_126.Defs

namespace Problems.Minif2f.mathd_algebra_126

-- Direct leaf proof: introduce binders, split the conjunction with `refine ⟨?_, ?_⟩`,
-- and discharge each component by `linarith` using `h₀ : 2*3 = x - 9` (⟹ x = 15)
-- and `h₁ : 2*-5 = y + 1` (⟹ y = -11). No sub-goals — both arms are visible linear facts.
theorem s634 : ∀ (x y : ℝ) (h₀ : 2 * 3 = x - 9) (h₁ : 2 * -5 = y + 1), x = 15 ∧ y = -11  := by
  intro x y h₀ h₁
  refine ⟨?_, ?_⟩
  · linarith
  · linarith

end Problems.Minif2f.mathd_algebra_126
