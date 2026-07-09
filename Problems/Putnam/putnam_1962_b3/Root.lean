import Mathlib
import Problems.Putnam.putnam_1962_b3.Defs

set_option linter.style.longLine false

open MeasureTheory

namespace Problems.Putnam.putnam_1962_b3

theorem main : ∀ (S : Set (EuclideanSpace ℝ (Fin 2)))
(hS : Convex ℝ S ∧ 0 ∈ S)
(htopo : (0 ∈ interior S) ∨ IsClosed S)
(hray : ∀ P : EuclideanSpace ℝ (Fin 2), P ≠ 0 → ∃ Q : EuclideanSpace ℝ (Fin 2), SameRay ℝ P Q ∧ Q ∉ S),
Bornology.IsBounded S := by sorry

end Problems.Putnam.putnam_1962_b3
