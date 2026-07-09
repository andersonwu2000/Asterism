import Mathlib
import Problems.Putnam.putnam_2025_b1.Defs

set_option linter.style.longLine false

open Affine EuclideanGeometry

namespace Problems.Putnam.putnam_2025_b1

theorem main : ∀ (color : EuclideanSpace ℝ (Fin 2) → Bool)
    (h : ∀ (s : Simplex ℝ (EuclideanSpace ℝ (Fin 2)) 2),
      (∀ i j : Fin 3, color (s.points i) = color (s.points j)) →
      color s.circumcenter = color (s.points 0)),
∃ c : Bool, ∀ P : EuclideanSpace ℝ (Fin 2), color P = c := by sorry

end Problems.Putnam.putnam_2025_b1
