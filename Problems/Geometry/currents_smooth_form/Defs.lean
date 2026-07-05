import Mathlib
import Library.Geometry.Currents.BoundarySquareZero

open scoped Distributions ContDiff
open TestFunction TopologicalSpace MeasureTheory
open Library.Geometry.Currents.BoundarySquareZero

namespace Problems.Geometry.currents_smooth_form

variable {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  [MeasurableSpace E] [OpensMeasurableSpace E] {Ω : Opens E} {k : ℕ}

/-- The **k-current of a smooth k-form** `w`, paired against test k-forms through a
continuous bilinear form `B` on k-covectors and integrated against a measure `μ`:
`ofSmoothForm B μ w (φ) = ∫ x, B (φ x) (w x) ∂μ`.

This is the smooth special case of the Federer-Fleming representation of a current
by a (co)vector field and a mass measure, `T(φ) = ∫ ⟨φ(x), w(x)⟩ d‖T‖(x)`, with the
pairing `⟨·,·⟩` supplied abstractly as `B` and the mass measure as `μ`. Keeping `B`
a parameter makes the embedding **metric-free at the definition level** (no inner
product is baked in — `B := ⟪·,·⟫` recovers the metric current as one instance) and
fully general over any real normed space `E`. Continuity of the resulting functional
on the LF test-form space is supplied for free by `TestFunction.integralAgainstBilinCLM`. -/
noncomputable def ofSmoothForm
    (B : (E [⋀^Fin k]→L[ℝ] ℝ) →L[ℝ] (E [⋀^Fin k]→L[ℝ] ℝ) →L[ℝ] ℝ)
    (μ : Measure E) (w : E → (E [⋀^Fin k]→L[ℝ] ℝ)) : Current Ω k :=
  TestFunction.integralAgainstBilinCLM B μ w

end Problems.Geometry.currents_smooth_form
