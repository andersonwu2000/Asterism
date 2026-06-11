---
problem: Geometry.stokes_bdry_compact
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_bdry_compact — the boundary ∂M of a compact manifold is compact

## Statement
`CompactSpace (Bdry n M)` where `Bdry n M = {x : M // x ∈ (𝓡∂ (n+1)).boundary M}`
and `M` is a compact `C^∞` `(n+1)`-manifold-with-boundary. (§6 — the
`instBdryCompact` instance the boundary integral needs.)

## Setting
`Bdry n M` is the boundary subtype of `M`. The boundary of a model-with-corners is
a closed set, so `Bdry n M` is a closed subspace of the compact `M`, hence compact.

## Lemma hints
- `Mathlib/Geometry/Manifold/ModelWithCorners` /
  `Mathlib/Geometry/Manifold/InteriorBoundary.lean` — `ModelWithCorners.boundary`,
  and that it is closed (`isClosed_boundary` or via `IsClosed` of the boundary set).
- `IsClosed.isCompact` (closed subset of compact space is compact) +
  `isCompact_iff_compactSpace` / `IsClosed.compactSpace` to get the `CompactSpace`
  instance on the subtype.
- Strategy: show the boundary set is closed, then transfer compactness to the
  subtype via the closed-subset-of-compact lemma.
