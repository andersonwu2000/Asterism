---
problem: Geometry.stokes_pullback
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_pullback — ι*φ is a smooth form on ∂M

## Statement
`pullbackBdryFun φ` is a `C^∞` section of `⋀ⁿ T*∂M` (the smoothness of the pullback
`ι* φ`). §A.7. Owns `faceEmbedL` (= `dι` in coordinates) and `pullbackBdryFun`.

## Setting
Cites P4 (`DiffForm`/`formBundleCore`/bundle instances), P5 (`formInCoord` +
`instFormBundleContMDiff`), `Bdry`, and `∂M`'s manifold structure (`instBdryChartedSpace`,
`isManifold_bdry`). `ι` becomes the linear `faceEmbed` in boundary-adapted charts, so
`dι = faceEmbedL` (constant); `ι*φ = compContinuousLinearMapCLM faceEmbedL ∘ (φ's coord rep)`.

## Lemma hints
- Section smoothness reduces (via `Trivialization.symmL` / `continuousLinearMapAt`) to
  smoothness of the coordinate map; `formInCoord` of a smooth `φ` is smooth (P5),
  `compContinuousLinearMapCLM faceEmbedL` is a fixed CLM (smooth), and `extChartAt` /
  `p.val` (the inclusion) are smooth on `∂M`.
- Mirror P5 (`Geometry.stokes_mextderiv`): explicit `ContMDiff` of the total-space map,
  fibre family pinned by `(E := …)`; `instFormBundleContMDiff` gives the smooth bundle.
- `contMDiff_faceEmbed` / `contDiff_faceProj` (Library `BdryIsManifold`) and the
  boundary-chart smoothness are available.
