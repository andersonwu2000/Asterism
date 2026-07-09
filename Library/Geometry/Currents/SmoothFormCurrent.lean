import Library.Geometry.Currents.BoundarySquareZero

/-!
# Embedding smooth differential forms as currents

This file constructs the map sending a smooth `k`-form `w : E → E [⋀^Fin k]→L[ℝ] ℝ` on an open
set `Ω ⊆ E` to the `k`-current `ofSmoothForm B μ w`, defined by integration against a
continuous bilinear pairing `B` on `k`-covectors and a Borel measure `μ`.

## Main definitions

- `ofSmoothForm`: the `k`-current `T` associated to a smooth `k`-form `w` and a continuous
  bilinear pairing `B`, given by `T(φ) := ∫ x, B (φ x) (w x) ∂μ`.

## Main statements

- `ofSmoothForm_apply`: evaluating `ofSmoothForm B μ w` on a test form `φ` yields the integral
  `∫ x, B (φ x) (w x) ∂μ`, provided `w` is locally integrable on `Ω`.

## Implementation notes

The pairing `B` is kept abstract to make the construction metric-free at the definition level.
Specialising `B := ⟪·, ·⟫` recovers the metric current. Continuity of the functional on the
LF test-form space follows from `TestFunction.integralAgainstBilinCLM`.
-/

open Library.Geometry.Currents.BoundarySquareZero
open TestFunction TopologicalSpace MeasureTheory
open scoped Distributions ContDiff

namespace Library.Geometry.Currents.SmoothFormCurrent

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

/-- Evaluating `ofSmoothForm B μ w` on a test `k`-form `φ` gives the integral
`∫ x, B (φ x) (w x) ∂μ`, provided `w` is locally integrable on `Ω` with respect to `μ`.

This unfolds the definition of `ofSmoothForm` via `TestFunction.integralAgainstBilinCLM`
and applies `integralAgainstBilinCLM_eq_integral`. -/
theorem ofSmoothForm_apply : ∀ {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    [MeasurableSpace E] [OpensMeasurableSpace E] {Ω : Opens E} {k : ℕ}
    (B : (E [⋀^Fin k]→L[ℝ] ℝ) →L[ℝ] (E [⋀^Fin k]→L[ℝ] ℝ) →L[ℝ] ℝ)
    (μ : Measure E) (w : E → (E [⋀^Fin k]→L[ℝ] ℝ)),
    LocallyIntegrableOn w Ω μ → ∀ (φ : 𝓓^{(⊤ : ℕ∞)}(Ω, E [⋀^Fin k]→L[ℝ] ℝ)),
    ofSmoothForm B μ w φ = ∫ x, B (φ x) (w x) ∂μ := by
  intro E _ _ _ _ Ω k B μ w hw φ
  rw [ofSmoothForm, TestFunction.integralAgainstBilinCLM_eq_integral hw]

end Library.Geometry.Currents.SmoothFormCurrent
