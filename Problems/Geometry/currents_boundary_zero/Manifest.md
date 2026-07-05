---
problem: Geometry.currents_boundary_zero
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.currents_boundary_zero — ∂∘∂ = 0 for de Rham currents

## Statement
For a de Rham `(k+2)`-current `T` on an open `Ω ⊆ E` (a continuous linear
functional on test forms; see `Defs.lean`), the boundary operator `∂`
(`boundary`, defined by `(∂T)(φ) = T(dφ)`) satisfies

`boundary (boundary T) = 0`

— the chain-complex relation `∂∘∂ = 0` of the currents complex.

## Setting
Second brick of the **de Rham currents → Federer-Fleming** foundation, building
directly on the first (harvested into the Library). `∂` is precomposition with
the test-form exterior-derivative CLM `extDerivCLM`; `∂∘∂ = 0` is the dual of
the test-form `d∘d = 0` already in the Library. This makes currents into a chain
complex (whose homology is, by de Rham, the cohomology of `Ω`).

## Strategic notes
Unfold both `boundary`s: `boundary (boundary T) = (T.comp (extDerivCLM (k+1)))
.comp (extDerivCLM k)`. Reassociate the continuous-linear-map composition
(`ContinuousLinearMap.comp_assoc`) to `T.comp ((extDerivCLM (k+1)).comp
(extDerivCLM k))`, rewrite the inner composition to `0` via the Library's
`extDerivCLM_comp_extDerivCLM_eq_zero`, then `ContinuousLinearMap.comp_zero`
closes it. Likely a clean leaf-bypass — no decomposition needed.

## Lemma hints
- `Library.Geometry.Manifold.ExtDerivCLMSquareZero.extDerivCLM_comp_extDerivCLM_eq_zero` : `(extDerivCLM (k+1)).comp (extDerivCLM k) = 0` — the Library d∘d=0 this reduces to.
- `Library.Geometry.Manifold.ExtDerivCLMSquareZero.extDerivCLM` : the exterior-derivative CLM `∂` precomposes with.
- `ContinuousLinearMap.comp_assoc` : `(f.comp g).comp h = f.comp (g.comp h)`.
- `ContinuousLinearMap.comp_zero` : `f.comp 0 = 0`.
