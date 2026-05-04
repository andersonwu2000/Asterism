import Mathlib

/-!
Problem-level shared definitions for the Sylvester–Gallai exercise.
Coordinate-free `Collinear` via determinant of `[p - r; q - r]`; avoids
`AffineSubspace` so the statement stays elementary.
-/

namespace Problems.sylvester_gallai

def Collinear (p q r : ℝ × ℝ) : Prop :=
  (p.1 - r.1) * (q.2 - r.2) = (p.2 - r.2) * (q.1 - r.1)

end Problems.sylvester_gallai
