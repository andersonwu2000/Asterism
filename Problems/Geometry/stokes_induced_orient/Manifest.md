---
problem: Geometry.stokes_induced_orient
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_induced_orient — the induced boundary orientation is smooth

## Statement
`inducedOrientFun` is a `C^∞` section of `⋀ⁿ T*∂M` (the smoothness of the induced
boundary orientation form `ι_ν μ`). §A.8. Owns `inducedOrientFun`.

## Setting
The boundary orientation Stokes selects is the contraction of `M`'s orientation `μ`
with the outward normal `ν = -e₀`, restricted to `∂M`. In coordinates:
`compContinuousLinearMapCLM faceEmbedL ((μ's coord rep).curryLeft (-e₀))`. Cites P11
(`OrientedManifold` + `refForm`), P10 (`faceEmbedL`), P5 (`formInCoord`), P4
(`DiffForm`/`formBundleCore`), `Bdry`, and `∂M`'s manifold structure (global instance
`isManifold_bdry`).

## Lemma hints
- Mirror P10 (`Geometry.stokes_pullback`): explicit `ContMDiff` of the total-space map,
  fibre family pinned by `(E := …)`; `instFormBundleContMDiff` gives the smooth bundle.
- Section smoothness reduces (via `Trivialization.symmL` / `continuousLinearMapAt`) to
  smoothness of the coordinate map. `formInCoord` of the smooth `refForm μ` is smooth
  (P5); `curryLeft (-e₀)` and `compContinuousLinearMapCLM faceEmbedL` are fixed CLMs
  (smooth); `extChartAt` / `p.val` (the `∂M` inclusion) are smooth.
- `ContinuousAlternatingMap.curryLeft`, `compContinuousLinearMapCLM`,
  `EuclideanSpace.basisFun`; the boundary-inclusion smoothness `bdry_val_contmdiff`
  (Library `BdryValSmooth`, from P10) is available.
