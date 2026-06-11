---
problem: Geometry.stokes_bdry_manifold
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_bdry_manifold — ∂M is a C^∞ n-manifold

## Statement
`IsManifold (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) ∞ (Bdry n M)` — the boundary `∂M` of a
`C^∞` `(n+1)`-manifold-with-boundary is itself a boundaryless `C^∞` `n`-manifold.
Owns the boundary `ChartedSpace` instance (atlas of `bdryChart`s, `mem_chart_source`
from P8). The Root is the smoothness of the boundary atlas (`HasGroupoid`).

## Setting
PARKED until P8 (`stokes_bdry_chartedspace`) migrates — the `ChartedSpace` instance
cites P8's `bdryChart` + `mem_chart_source`. Transition maps of `∂M` are `M`'s
boundary-chart transitions restricted to the face `{x₀=0}` and pushed through
`faceProj`/`faceEmbed`; these are `C^∞` because `M`'s transitions are and the face
embedding/projection are linear (hence smooth).

## Lemma hints
- `IsManifold` / `HasGroupoid` over `contDiffGroupoid`; reduce to: every transition
  `bdryChart i ≫ₕ (bdryChart j).symm` is `C^∞` on its domain.
- The transition unfolds to `faceProj ∘ (extChartAt p_j ∘ extChartAt p_i .symm) ∘ faceEmbed`
  on the face; `M`'s transition `extChartAt p_j ∘ (extChartAt p_i).symm` is `ContDiffOn`
  (`contDiffOn_extChartAt` / the `IsManifold` structure of `M`), and `faceProj`/`faceEmbed`
  are continuous-linear hence `C^∞`.
- `contDiffGroupoid`, `StructureGroupoid.compatible`, `contDiffOn_of_...`.
