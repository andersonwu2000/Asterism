import Mathlib

open Classical

namespace Complex

/--
Residue of `f` at the isolated singularity `z₀`.

When `f` is analytic on a punctured ball `Metric.ball z₀ R \ {z₀}` for
some `R > 0`, define `residue f z₀ := (1/(2πi)) · ∮ z in C(z₀, R/2), f z`
for one such `R` chosen classically. The integration circle sits
strictly inside the analytic domain, so the integral is well-defined.
Independence from the chosen `R` is the content of
`Residue.contour_deformation_annulus`.

Outside the regime (no positive analytic radius exists), residue = 0.
-/
noncomputable def residue (f : ℂ → ℂ) (z₀ : ℂ) : ℂ :=
  if h : ∃ R : ℝ, 0 < R ∧ AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}) then
    (1 / (2 * Real.pi * Complex.I)) *
      ∮ z in C(z₀, Classical.choose h / 2), f z
  else 0

end Complex
