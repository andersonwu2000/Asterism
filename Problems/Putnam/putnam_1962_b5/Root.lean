import Mathlib
import Problems.Putnam.putnam_1962_b5.Defs

set_option linter.style.longLine false

open MeasureTheory

namespace Problems.Putnam.putnam_1962_b5

theorem main : ∀ (n : ℤ)
(ng1 : n > 1),
(3 * (n : ℝ) + 1) / (2 * n + 2) < ∑ i : Finset.Icc 1 n, ((i : ℝ) / n) ^ (n : ℝ) ∧ ∑ i : Finset.Icc 1 n, ((i : ℝ) / n) ^ (n : ℝ) < 2 := by sorry

end Problems.Putnam.putnam_1962_b5
