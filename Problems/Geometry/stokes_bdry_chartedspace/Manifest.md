---
problem: Geometry.stokes_bdry_chartedspace
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_bdry_chartedspace — assemble the boundary chart + mem_chart_source

## Statement
`p ∈ (bdryChart p).source` for every boundary point `p` — the `mem_chart_source`
axiom of the boundary `ChartedSpace`. Owns `bdryChart`, the boundary chart as an
`OpenPartialHomeomorph` (assembled from the cited chart data + partial-equiv laws +
topological laws, all proven).

## Setting
PARKED until P7c (`stokes_bdry_chart_topo`) migrates — `bdryChart`'s topological
fields cite P7c's `chart_*_is_open` / `*_continuous_on`, whose Library module is not
yet final (P7c migrate stalled on a librarian gap).

`(bdryChart p).source = chartSource p = Subtype.val ⁻¹' (extChartAt (𝓡∂ (n+1)) p.val).source`,
and `p.val ∈ (extChartAt (𝓡∂ (n+1)) p.val).source`, so `p ∈ chartSource p`.

## Lemma hints
- `mem_extChartAt_source` / `mem_chart_source` — a point is in its own chart source.
- `Set.mem_preimage`, `chartSource` unfolds to the `Subtype.val` preimage.
