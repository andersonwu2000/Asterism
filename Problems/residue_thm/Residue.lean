/-
Copyright (c) 2026 TODO. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: TODO (your name)
-/
import Mathlib

/-!
# Winding number and residue of a complex function

This is a **PR-shaped review draft** (not wired into the Asterism build) of how
`Complex.windingNumber` and `Complex.residue` would be contributed to Mathlib.

## Conventions, copied from `fderivWithin`

The template is `fderivWithin` (`Mathlib/Analysis/Calculus/FDeriv/Defs.lean`):
```
irreducible_def fderivWithin (f) (s) (x) :=
  if HasFDerivWithinAt f 0 s x then 0
  else if h : DifferentiableWithinAt 𝕜 f s x then Classical.choose h else 0
```
We reuse its three hygiene choices:

* **Named regime predicate.** The "good" domain is a *named* `Prop`
  (`HasIsolatedSingularityAt`), never an inline `∃`.  A named predicate carries a
  reusable API and lets every lemma state the regime identically — exactly how
  `fderivWithin` uses `DifferentiableWithinAt`, `integral` uses `Integrable`, and
  `finrank` uses `Module.Finite`.
* **`irreducible_def`.** `windingNumber`/`residue` are irreducible, sealing the
  `Classical.choose` away from definitional unfolding; users interact only through the
  characterising lemmas (`windingNumber_spec`, `residue_eq_inv_two_pi_I_mul_circleIntegral`).
* **Junk value `0` off-regime.** Total functions; outside the regime they return `0`,
  documented by a named lemma and *never asserted to be meaningful* (the value carries no
  mathematical content there).  This is what lets them sit inside `∑ a ∈ T, …`.

## Regime: isolated singularities (essential singularities included)

`HasIsolatedSingularityAt f z₀` says `f` is analytic on *some* punctured ball
`Metric.ball z₀ R \ {z₀}`.  This **includes essential singularities** (`exp (1/z)` at `0`),
where the residue theorem still holds.  It is deliberately **not** `MeromorphicAt`, which is
narrower (finite-order poles only) and would make the theorem *false* at essential
singularities (silently reading the junk `0`).  An equivalent, often-preferred hypothesis
form is the filter idiom `∀ᶠ z in 𝓝[≠] z₀, AnalyticAt ℂ f z`; the explicit-ball form is the
definition because the contour integral needs a concrete radius.
-/

namespace Complex

/-! ### Isolated-singularity regime -/

/-- `f` has an isolated singularity (removable, a pole, or essential) at `z₀`: it is
analytic on some punctured ball around `z₀`.  This is the regime on which `residue` is
meaningful. -/
def HasIsolatedSingularityAt (f : ℂ → ℂ) (z₀ : ℂ) : Prop :=
  ∃ R : ℝ, 0 < R ∧ AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})

/-- Analyticity on a full ball (an absent/removable singularity) is in particular an
isolated singularity.  Sample lemma: the named predicate has a reusable API. -/
theorem hasIsolatedSingularityAt_of_analyticOn {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R)) : HasIsolatedSingularityAt f z₀ :=
  ⟨R, hR, hf.mono Set.diff_subset⟩

/-! ### Winding number -/

open Classical in
/-- Winding number of a C¹ closed path `γ` around `a`: the integer period of
`∫ t in 0..1, γ'/(γ - a)` divided by `2πi` when it exists, else the junk value `0`.
Sealed `irreducible_def`; rewrite with `windingNumber_spec`. -/
noncomputable irreducible_def windingNumber (γ : ℝ → ℂ) (a : ℂ) : ℤ :=
  if h : ∃ k : ℤ,
        (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 2 * Real.pi * Complex.I * k
    then Classical.choose h
    else 0

/-- Off-regime junk value: with no integral period, the winding number is `0`. -/
@[simp]
theorem windingNumber_eq_zero_of_not_exists {γ : ℝ → ℂ} {a : ℂ}
    (h : ¬ ∃ k : ℤ,
        (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 2 * Real.pi * Complex.I * k) :
    windingNumber γ a = 0 := by
  rw [windingNumber_def, dif_neg h]

/-- Characterising property: in the regime where an integer period exists, the integral of
`γ'/(γ - a)` is exactly `2πi` times the winding number.  The `Classical.choose` of the
definition is never exposed. -/
theorem windingNumber_spec {γ : ℝ → ℂ} {a : ℂ}
    (h : ∃ k : ℤ,
        (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 2 * Real.pi * Complex.I * k) :
    (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a))
      = 2 * Real.pi * Complex.I * (windingNumber γ a : ℂ) := by
  rw [windingNumber_def, dif_pos h]
  exact Classical.choose_spec h

/-! ### Residue -/

open Classical in
/-- Residue of `f` at an isolated singularity `z₀`: `(1/(2πi)) · ∮ C(z₀, R/2) f` for a
classically chosen punctured-ball radius `R`, else the junk value `0`.  Independence of the
value from the radius is the content of `residue_eq_inv_two_pi_I_mul_circleIntegral`.
Sealed `irreducible_def`. -/
noncomputable irreducible_def residue (f : ℂ → ℂ) (z₀ : ℂ) : ℂ :=
  if h : HasIsolatedSingularityAt f z₀ then
    (1 / (2 * Real.pi * Complex.I)) *
      ∮ z in C(z₀, Classical.choose h / 2), f z
  else 0

/-- Off-regime junk value: with no analytic punctured ball, the residue is `0`. -/
@[simp]
theorem residue_eq_zero_of_not_isolated {f : ℂ → ℂ} {z₀ : ℂ}
    (h : ¬ HasIsolatedSingularityAt f z₀) : residue f z₀ = 0 := by
  rw [residue_def, dif_neg h]

/-- **Characterising property of the residue.**  If `f` is analytic on the punctured ball
`Metric.ball z₀ R \ {z₀}` and `0 < r < R`, the residue is recovered as the normalised
contour integral over *any* such circle `C(z₀, r)`.  Radius-independence is the
contour-deformation content (Cauchy's theorem on the annulus between two circles), and is
the genuine mathematical content the Asterism framework proves. -/
theorem residue_eq_inv_two_pi_I_mul_circleIntegral {f : ℂ → ℂ} {z₀ : ℂ} {R r : ℝ}
    (hR0 : 0 < R) (hR : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (hr : 0 < r) (hrR : r < R) :
    residue f z₀ = (1 / (2 * Real.pi * Complex.I)) * ∮ z in C(z₀, r), f z := by
  sorry

end Complex

/-! ### Target theorem (the payoff)

The residue theorem stated on top of the total `Complex.windingNumber` and
`Complex.residue`.  The `∑ a ∈ T, …` typechecks cleanly precisely because both are total
functions — the convention pays off here.  Its proof is the goal of the Asterism
`residue_thm` problem; left `sorry` in this draft. -/

theorem residue_theorem
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hSC : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 2 * Real.pi * Complex.I *
      ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * Complex.residue f a := by
  sorry
