---
problem: Geometry.currents_smooth_form
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.currents_smooth_form — smooth k-form as a de Rham current

## Statement
A locally integrable **smooth k-form** `w : E → (E [⋀^Fin k]→L[ℝ] ℝ)`, together
with a continuous bilinear pairing `B` on k-covectors, embeds as a k-current
`ofSmoothForm B μ w : Current Ω k` (see `Defs.lean`). The defining evaluation is

`ofSmoothForm B μ w φ = ∫ x, B (φ x) (w x) ∂μ`

for any locally-integrable `w` (`hw : LocallyIntegrableOn w Ω μ`) and test k-form
`φ`.

## Setting
Third brick of the **de Rham currents → Federer-Fleming** foundation, on top of the
harvested `Library.Geometry.Currents.BoundarySquareZero` (`Current`, `boundary`,
`∂∘∂=0`). It realizes the smooth special case of the FF representation
`T(φ) = ∫ ⟨φ, w⟩ d‖T‖`: the orienting field is `w`, the mass measure is `μ`, and the
pairing `⟨·,·⟩` is supplied abstractly as `B` (so no inner product is baked in;
`B := ⟪·,·⟫` recovers the metric current as one instance). Metric-free at the
definition level and general over any real normed `E`. The continuity of the
functional on the LF test-form space is supplied by Mathlib's
`TestFunction.integralAgainstBilinCLM`, which lifts the fixed-compact-support
construction across the inductive limit for free.

(Design note: the FF-canonical *covector·vector* evaluation pairing would put the
field in the dual `Λ^k →L ℝ`, whose `ContinuousENorm` instance is currently missing
in Mathlib for alternating-map CLM spaces — an instance diamond on
`(ContinuousAlternatingMap) →L ℝ`. Parametrizing by `B` with the field in `Λ^k`
sidesteps that gap while staying more general.)

## Strategic notes
Unfold `ofSmoothForm` to `TestFunction.integralAgainstBilinCLM B μ w` applied to
`φ`. Rewrite with `TestFunction.integralAgainstBilinCLM_eq_integral hw` (discharging
its `LocallyIntegrableOn w Ω μ` side condition with the hypothesis `hw`) to land
directly on `∫ x, B (φ x) (w x) ∂μ`. This closes the goal — a clean leaf-bypass, no
decomposition needed. (Verified: `rw [ofSmoothForm,
TestFunction.integralAgainstBilinCLM_eq_integral hw]` alone discharges it.)

## Lemma hints
- `TestFunction.integralAgainstBilinCLM_eq_integral` : `(hφ : LocallyIntegrableOn φ Ω μ) → integralAgainstBilinCLM B μ φ f = ∫ x, B (f x) (φ x) ∂μ` — the LF eval lemma; here `f := φ` (the test form), the lemma's `φ := w`, and `B` is our pairing.
- `ofSmoothForm` (from `Defs.lean`) : unfold to expose `integralAgainstBilinCLM`.
