---
problem: Geometry.stokes_bdry_chart
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_bdry_chart — boundary chart data is a PartialEquiv

## Statement
The boundary chart data at `p` (`chartToFun`/`chartInvFun`/`chartSource`/`chartTarget`)
satisfies the four partial-equiv laws: `map_source`, `map_target`, `left_inv`,
`right_inv` on `source`/`target`.

## Setting
Cites `Library.Geometry.ManifoldBoundary` for `Bdry`, `faceEmbed`, and
`faceEmbed_symm_mem_boundary`. The chart is `M`'s extended chart at `p` projected to
the boundary face via `faceProj` (the left inverse of `faceEmbed` on `{x₀=0}`);
`invFun` is guarded (off-target → `p`).

Key facts the proof needs:
- `faceProj (faceEmbed z) = z` (mutual inverses on the face).
- For a chart-source boundary point `q.val`, `extChartAt p.val q.val` lies on the
  face `{x₀=0}` (boundary maps to model boundary), so `faceEmbed (faceProj …) = …`.
- `extChartAt`'s `map_source`/`map_target`/`left_inv`/`right_inv` on source/target.

## Lemma hints
- `Mathlib/Geometry/Manifold/InteriorBoundary.lean` — boundary ↦ model-boundary
  under charts (the converse direction of the Library lemmas already proved).
- `extChartAt_source`, `extChartAt_target`, `PartialEquiv.map_source`,
  `PartialEquiv.left_inv`, `PartialEquiv.right_inv`.
- `EuclideanSpace.basisFun_apply`, `Fin.succ_ne_zero` for the `faceProj`/`faceEmbed`
  coordinate round-trip.
