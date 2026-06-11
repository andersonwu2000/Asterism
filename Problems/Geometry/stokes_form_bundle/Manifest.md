---
problem: Geometry.stokes_form_bundle
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_form_bundle — the ⋀ᵏ T*M bundle has C^∞ transitions

## Statement
`(formBundleCore I k).IsContMDiff I ∞` — the vector-bundle core of `⋀ᵏ T*M` has
`C^∞` transition functions. (§A.4. Owns `formBundleCore` / the bundle instances /
`DiffForm`.)

## Setting
Cites `Library.Geometry.Manifold.FormCoordChange*` for `formCoordChange` and its
three coherence lemmas (`formCoordChange_self`, `continuousOn_formCoordChange`,
`formCoordChange_comp`), which become the `VectorBundleCore` fields. The transition
`formCoordChange I k i j = compContinuousLinearMapCLM ((tangentBundleCore I M).coordChange j i)`.

## Lemma hints
- `Mathlib/Geometry/Manifold/VectorBundle/Tangent.lean` — `tangentBundleCore`,
  its `IsContMDiff` / smoothness (`(tangentBundleCore I M).contMDiff_coordChange` or
  the `ContMDiffVectorBundle`/`SmoothManifoldWithCorners` machinery).
- `ContinuousAlternatingMap.compContinuousLinearMapCLM` is a `ContinuousLinearMap`,
  hence `C^∞`; smoothness of `coordChange` is preserved under post-composition by a
  fixed CLM. Reduce `VectorBundleCore.IsContMDiff` to the tangent core's via the
  smooth dependence of `compContinuousLinearMapCLM (tangent coordChange)` on the base.
- `VectorBundleCore.IsContMDiff` unfolds to `ContMDiffOn` of each `coordChange i j`
  as a map into the operator space.
