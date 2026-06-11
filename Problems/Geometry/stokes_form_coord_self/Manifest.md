---
problem: Geometry.stokes_form_coord_self
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_form_coord_self — `⋀ᵏ T*M` transition fixes the fibre on a self-overlap

## Statement
For the form-bundle transition `formCoordChange I k i i` at a self-overlap,
`formCoordChange I k i i x v = v` for every `x` in the base set and every `v`.
(§A.1 of the Stokes form-bundle construction.)

## Setting
`formCoordChange I k i j x := compContinuousLinearMapCLM ((tangentBundleCore I M).coordChange j i x)`
is the transition of the bundle `⋀ᵏ T*M` of alternating `k`-forms on the tangent
spaces of a `C^∞` manifold `M` (model `I`). It is the contravariant
(precomposition) push of the tangent transition. This obligation is the
`coordChange_self` field needed to make `formCoordChange` a `VectorBundleCore`.

## Lemma hints
- `Mathlib/Geometry/Manifold/VectorBundle/Tangent.lean` — `tangentBundleCore`,
  `VectorBundleCore.coordChange_self` (the tangent self-overlap identity).
- `Mathlib/Topology/Algebra/Module/Alternating/Basic.lean` /
  `Mathlib/Analysis/.../Alternating` — `ContinuousAlternatingMap.compContinuousLinearMapCLM`,
  its action on `ContinuousLinearMap.id` (precomposition by `id` is `id`).
- Strategy: rewrite the tangent `coordChange_self` to turn the inner CLM into
  `ContinuousLinearMap.id`, then `compContinuousLinearMapCLM id = id`.
