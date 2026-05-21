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

## Strategic notes
Algebraic-topology route (operator preference; matches the standard
undergraduate proof):

- Construct the universal cover `ℝ → Circle` via
  `t ↦ ⟨Complex.exp (2 * π * I * t), ...⟩` (the unit-sphere membership
  follows from `Complex.abs_exp_ofReal_mul_I` after rearranging).
- Path lifting: every path in `Circle` starting at `1` lifts uniquely to
  a path in `ℝ` starting at `0`.
- Homotopy lifting: homotopic loops lift to paths with the same endpoint
  in `ℝ`, giving a well-defined map `π₁(Circle, 1) → ℤ` via the
  lifted-endpoint integer.
- Group homomorphism (concatenation ↔ addition) + bijection ⇒
  `MulEquiv` to `Multiplicative ℤ`.

Do NOT use winding-number formulations (`Complex.windingNumber`,
`exp_winding_integral_eq_one`, `circleIntegral`-based arguments, etc.).
Those live in residue_thm's analytic toolkit and would short-circuit
the stress test — the point is to surface gaps in covering-space /
path-homotopy machinery, not to reuse a different topic's lemmas.

Mathlib's covering-space theory is incomplete: no `UniversalCover` for
topological spaces, no deck-transformation group, only homotopy-lifting
(`Topology/Homotopy/Lifting.lean`) without covering-map foundations.
Expect the framework to construct the minimal subset needed
for this proof (path-lifting + monodromy-style endpoint integer).
