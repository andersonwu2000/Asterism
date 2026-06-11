---
problem: Geometry.stokes_bdry_chart_topo
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_bdry_chart_topo — the boundary chart is open + continuous

## Statement
For each boundary point `p`, `chartSource p` and `chartTarget p` are open, and
`chartToFun p` / `chartInvFun p` are continuous on `source` / `target`. (The
topological half of the boundary chart; with `chart_axioms` it assembles the
`OpenPartialHomeomorph`.)

## Setting
Cites the chart data from `Library.Geometry.ManifoldBoundary.Defs`
(`chartToFun = faceProj ∘ extChartAt`, `chartInvFun` = guarded `extChartAt.symm ∘ faceEmbed`,
`chartSource = Subtype.val ⁻¹' (extChartAt …).source`,
`chartTarget = faceProj '' ((extChartAt …).target ∩ {w | w 0 = 0})`).

## Lemma hints
- **open_source**: `chartSource p = Subtype.val ⁻¹' (extChartAt …).source`; the chart
  source is open (`extChartAt_source` / `isOpen_extChartAt_source` or
  `PartialEquiv`/`PartialHomeomorph.open_source`), pulled back by the continuous
  `Subtype.val` (`IsOpen.preimage continuous_subtype_val`).
- **continuousOn_toFun**: `faceProj` is continuous (a continuous linear map /
  coordinate projection on `EuclideanSpace`); `extChartAt` is `ContinuousOn` its
  source (`continuousOn_extChartAt`); `Subtype.val` is continuous. Compose via
  `ContinuousOn.comp` / `Continuous.comp_continuousOn`.
- **continuousOn_invFun**: on `chartTarget`, the guard takes the `then` branch, so
  `chartInvFun p z = (extChartAt …).symm (faceEmbed z)` there; `faceEmbed` is
  continuous (finite sum of `• basis`), `extChartAt.symm` is `ContinuousOn` its
  target (`continuousOn_extChartAt_symm`), and the result is a `Subtype.val`-fibre.
  Use `ContinuousOn.congr` to drop the guard on the target, then compose.
- **open_target**: `chartTarget p = faceProj '' ((extChartAt …).target ∩ {w | w 0 = 0})`.
  `faceProj` restricted to the face `{w | w 0 = 0}` is a homeomorphism onto
  `EuclideanSpace ℝ (Fin n)` (its inverse is `faceEmbed`); `(extChartAt …).target` is
  open, so its intersection with the face is open in the face subspace, and the
  homeomorphic image is open. Consider `faceEmbed ⁻¹' target` (open by continuity of
  `faceEmbed`) and `faceProj_image_eq_faceEmbed_preimage` style identities, or
  `IsOpenMap` of the projection on the face.

## Notes
This is the analytic crux of the boundary-manifold construction (`open_target` and
`continuousOn_invFun` are the hard parts — the face-subspace homeomorphism). If the
4-way conjunction stalls, it splits cleanly: easy pair (open_source, continuousOn_toFun)
vs hard pair (open_target, continuousOn_invFun).
