---
problem: pi1_circle
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# pi1_circle — fundamental group of the circle

## Statement
Nonempty (FundamentalGroup Circle 1 ≃* Multiplicative ℤ)

## Setting
- `Circle := Submonoid.unitSphere ℂ`
  (`Mathlib/Analysis/Complex/Circle.lean`)
- `FundamentalGroup X x := End (FundamentalGroupoid.mk x)`
  (`Mathlib/AlgebraicTopology/FundamentalGroupoid/FundamentalGroup.lean`)
- basepoint `(1 : Circle)`, canonical unit element of the unit-sphere
  submonoid
- conclusion: π₁(S¹) ≅ ℤ as multiplicative groups (path concatenation
  corresponds to integer addition under the exponential cover)

## Lemma hints
- `Circle.exp : C(ℝ, Circle)`, `Circle.exp_zero`, `Circle.exp_add`,
  `Circle.periodic_exp`, `Circle.exp_eq_exp`, `Circle.exp_eq_one`
  (`Mathlib/Analysis/SpecialFunctions/Complex/Circle.lean`)
- `Circle.isCoveringMap_exp : IsCoveringMap Circle.exp` (same file)
- `IsCoveringMap.liftPath`, `liftPath_lifts`, `liftPath_zero`,
  `liftPath_trans`, `IsCoveringMap.HomotopyLift`,
  `IsCoveringMap.monodromy`, `monodromy_refl`, `monodromy_trans_apply`,
  `monodromy_bijective`, `IsCoveringMap.existsUnique_continuousMap_lifts`
  (`Mathlib/Topology/Homotopy/Lifting.lean`)
- `FundamentalGroup.toPath` / `FundamentalGroup.fromPath` bridge
  `FundamentalGroup Circle 1` with `Path.Homotopic.Quotient (1:Circle) 1`

## Strategic notes
Algebraic-topology route (operator preference; matches the standard
undergraduate proof). Use Mathlib's existing covering-map machinery —
do NOT rebuild `IsCoveringMap Circle.exp`, do NOT redefine `Circle.exp`,
do NOT build a new `liftPath`.

Standard assembly:
- For a loop `γ : Path (1:Circle) 1`, lift via
  `Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0 (by simp)`
  to a path in `ℝ` starting at 0.
- The lifted endpoint `Γ(1) : ℝ` satisfies `Circle.exp (Γ 1) = 1`, so
  by `Circle.exp_eq_one` it lies in `2π · ℤ` — define `winding γ : ℤ`
  via `Classical.choose` on that existential, with characterizing
  equation `(Γ 1 : ℝ) = winding γ * (2 * π)`.
- Homotopy invariance: `IsCoveringMap.monodromy` already packages the
  lifted endpoint as a function on `Path.Homotopic.Quotient`, so
  `winding` descends to `FundamentalGroup Circle 1` without re-deriving
  homotopy lifting from scratch.
- Group-hom: `monodromy_refl` gives `winding 1 = 0`;
  `monodromy_trans_apply` gives `winding (a * b) = winding a + winding b`.
- Bijection: `monodromy_bijective` + the standard-loop construction
  `γ_n : Path (1:Circle) 1` with `winding γ_n = n` (e.g. via
  `Circle.exp ∘ (·  * n * (2 * π))` traced over `[0, 1]`).
- Assemble: `MulEquiv` from `FundamentalGroup Circle 1` to
  `Multiplicative ℤ` via `winding` + its inverse.

Do NOT use winding-number formulations (`Complex.windingNumber`,
`exp_winding_integral_eq_one`, `circleIntegral`-based arguments).
Those live in residue_thm's analytic toolkit and would short-circuit
the stress test — the point is to exercise path-homotopy / quotient
group / monodromy reasoning, not to reuse a different topic's
contour-integral lemmas.
