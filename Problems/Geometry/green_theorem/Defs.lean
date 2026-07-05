import Mathlib

open MeasureTheory Real
open scoped ContDiff

namespace Problems.Geometry.green_theorem

/-- Boundary parametrization of the closed unit disk: the unit circle
`θ ↦ (cos θ, sin θ)`, traversed once counterclockwise on `[0, 2π]`. -/
noncomputable def circle (θ : ℝ) : EuclideanSpace ℝ (Fin 2) := !₂[Real.cos θ, Real.sin θ]

/-- The counterclockwise boundary line integral `∮_∂D (P dx + Q dy)`, with the
unit circle parametrized by `circle`. Here `dx = -sin θ dθ`, `dy = cos θ dθ`. -/
noncomputable def lineIntegral (P Q : EuclideanSpace ℝ (Fin 2) → ℝ) : ℝ :=
  ∫ θ in (0 : ℝ)..(2 * π),
    P (circle θ) * (-Real.sin θ) + Q (circle θ) * Real.cos θ

/-- The double integral `∬_D (∂Q/∂x − ∂P/∂y)` of the scalar curl over the closed
unit disk `D = closedBall 0 1`. The partials are the directional Fréchet
derivatives along the standard basis vectors of `EuclideanSpace ℝ (Fin 2)`. -/
noncomputable def doubleIntegral (P Q : EuclideanSpace ℝ (Fin 2) → ℝ) : ℝ :=
  ∫ p in Metric.closedBall (0 : EuclideanSpace ℝ (Fin 2)) 1,
    (fderiv ℝ Q p (EuclideanSpace.single 0 1)
      - fderiv ℝ P p (EuclideanSpace.single 1 1)) ∂volume

end Problems.Geometry.green_theorem
