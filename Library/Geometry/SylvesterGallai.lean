import Mathlib

/-!
# Sylvester–Gallai — plane-geometry primitive

`Collinear` migrated verbatim (statement) from
`Problems.sylvester_gallai` (Asterism Librarian, 2026-05-30):
self-contained, depends only on Mathlib.

Coordinate-free collinearity via the determinant of `[p - r; q - r]`;
avoids `AffineSubspace` so the statement stays elementary.
-/

namespace Library.Geometry.SylvesterGallai

/-- Collinearity of three plane points, via the vanishing signed-area
determinant of `[p - r; q - r]`. -/
def Collinear (p q r : ℝ × ℝ) : Prop :=
  (p.1 - r.1) * (q.2 - r.2) = (p.2 - r.2) * (q.1 - r.1)

end Library.Geometry.SylvesterGallai
