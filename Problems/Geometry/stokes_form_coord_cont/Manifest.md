---
problem: Geometry.stokes_form_coord_cont
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_form_coord_cont — `⋀ᵏ T*M` transition is continuous on the overlap

## Statement
`ContinuousOn (formCoordChange I k i j) (baseSet i ∩ baseSet j)` for the form-bundle
transition. (§A.2 of the Stokes form-bundle construction — the
`continuousOn_coordChange` field of the `VectorBundleCore`.)

## Setting
`formCoordChange I k i j x := compContinuousLinearMapCLM ((tangentBundleCore I M).coordChange j i x)`
is the transition of `⋀ᵏ T*M` (alternating `k`-forms on `TM`) for a `C^∞` manifold
`M`. Continuity must hold on the chart overlap `baseSet i ∩ baseSet j`.

## Lemma hints
- `Mathlib/Geometry/Manifold/VectorBundle/Tangent.lean` —
  `tangentBundleCore`, `VectorBundleCore.continuousOn_coordChange`.
- `ContinuousAlternatingMap.compContinuousLinearMapCLM` — continuous (it is a CLM);
  compose its continuity with the tangent transition's `ContinuousOn`.
- Strategy: `compContinuousLinearMapCLM` is itself continuous, so
  `ContinuousOn` reduces to the tangent `continuousOn_coordChange` via
  `ContinuousOn.comp` / `Continuous.comp_continuousOn`.
