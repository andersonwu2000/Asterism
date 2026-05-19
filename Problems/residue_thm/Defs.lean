import Mathlib

namespace Complex

open Classical in
/--
Winding number of a C¹ closed path `γ : ℝ → ℂ` around a point `a ∈ ℂ`.

Defined classically: if there exists an integer `k : ℤ` such that
`∫ t in 0..1, deriv γ t / (γ t - a) = 2πi · k`, return that `k`;
otherwise return `0`.

For C¹ closed paths whose image avoids `a`, such a `k` always exists
(integrality theorem). Outside that hypothesis class the default `0` makes
the function total without committing to a value.
-/
noncomputable def windingNumber (γ : ℝ → ℂ) (a : ℂ) : ℤ :=
  if h : ∃ k : ℤ,
        (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 2 * Real.pi * Complex.I * k
    then Classical.choose h
    else 0

/--
Residue of `f` at the isolated singularity `z₀`.

When `f` is analytic on a punctured ball `Metric.ball z₀ R \ {z₀}` for
some `R > 0`, define `residue f z₀ := (1/(2πi)) · ∮ z in C(z₀, R/2), f z`
for one such `R` chosen classically. Independence from the chosen `R`
follows from contour deformation on the annulus.

Outside the regime (no positive analytic radius exists), residue = 0.
-/
noncomputable def residue (f : ℂ → ℂ) (z₀ : ℂ) : ℂ :=
  if h : ∃ R : ℝ, 0 < R ∧ AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}) then
    (1 / (2 * Real.pi * Complex.I)) *
      ∮ z in C(z₀, Classical.choose h / 2), f z
  else 0

end Complex
