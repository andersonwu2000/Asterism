import Mathlib
import Problems.Minif2f.mathd_algebra_101.Defs

namespace Problems.Minif2f.mathd_algebra_101

-- Direct leaf: the hypothesis x^2 - 5x - 4 ≤ 10 rewrites to (x+2)(x-7) ≤ 0.
-- Split the conjunction and discharge each bound via nlinarith using sq_nonneg hints.
theorem s522 : ∀ (x : ℝ) (h₀ : x ^ 2 - 5 * x - 4 ≤ 10), x ≥ -2 ∧ x ≤ 7  := by
  intro x h₀
  refine ⟨?_, ?_⟩
  · nlinarith [sq_nonneg (x + 2), sq_nonneg (x - 7), sq_nonneg (2 * x - 5)]
  · nlinarith [sq_nonneg (x + 2), sq_nonneg (x - 7), sq_nonneg (2 * x - 5)]

end Problems.Minif2f.mathd_algebra_101
