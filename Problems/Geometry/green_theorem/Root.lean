import Mathlib
import Problems.Geometry.green_theorem.Defs

open MeasureTheory Real
open scoped ContDiff

namespace Problems.Geometry.green_theorem

-- main: Green's theorem on the closed unit disk. For smooth `P, Q` on the
-- Euclidean plane, the counterclockwise boundary line integral of `P dx + Q dy`
-- equals the double integral of the scalar curl `∂Q/∂x − ∂P/∂y` over the disk.
-- To be proved via the abstract Stokes theorem in the Library, NOT via Mathlib's
-- classical divergence theorem (forbidden) — see Manifest for the bridge.
theorem main : ∀ (P Q : EuclideanSpace ℝ (Fin 2) → ℝ),
    ContDiff ℝ ∞ P → ContDiff ℝ ∞ Q →
    lineIntegral P Q = doubleIntegral P Q := by
  sorry

end Problems.Geometry.green_theorem
