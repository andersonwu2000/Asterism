import Mathlib
import Problems.Putnam.putnam_1962_a1.Defs

set_option linter.style.longLine false

open MeasureTheory

namespace Problems.Putnam.putnam_1962_a1

theorem main : ∀ (S : Set (ℝ × ℝ))
(hS : S.ncard = 5)
(hnoncol : ∀ s ⊆ S, s.ncard = 3 → ¬Collinear ℝ s),
∃ T ⊆ S, T.ncard = 4 ∧ ¬∃ t ∈ T, t ∈ convexHull ℝ (T \ {t}) := by sorry

end Problems.Putnam.putnam_1962_a1
