---
problem: Geometry.stokes_closed
library: false
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_closed — exact top forms integrate to zero on a closed manifold

## Statement
On a compact oriented `(n+1)`-manifold-with-boundary `M` whose boundary `∂M` is empty
(`IsEmpty (Bdry n M)` — i.e. `M` is closed), the integral of any exact top form vanishes:
`∫_M dφ = 0`. A direct corollary of the generalized Stokes theorem
(`∫_M dφ = ∫_∂M ι*φ`): the boundary integral is over an empty manifold, hence zero.

## Setting
Regression smoke for the knowledge-base / context work — **not** harvested into the
Library (`library: false`); it will be re-proved later. The proof must cite the proved
Stokes keystone, so this goal guards the Library-citation plumbing end to end.

## Lemma hints
- `Library.Geometry.Manifold.PerBumpStokes.integral_mextDeriv_eq_integral_pullbackBdry` :
  the proved Stokes equality `∫_M dφ = ∫_∂M ι*φ`. Rewrite the goal with it.
- `Library.Geometry.Manifold.StokesIntegral.integral_zero_of_localCoeff_zero` :
  `(∀ x y, localCoeff φ x y = 0) → DiffForm.integral φ = 0`. Discharge the resulting
  boundary integral vacuously — `[IsEmpty (Bdry n M)]` means no boundary point `x` exists,
  so the hypothesis holds by `fun x => isEmptyElim x`.
