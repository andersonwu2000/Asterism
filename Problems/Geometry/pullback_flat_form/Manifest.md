---
problem: Geometry.pullback_flat_form
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# Geometry.pullback_flat_form — pullback of a flat test k-form is a smooth bundle section

## Statement
∀ {n k : ℕ} {N : Type*} [TopologicalSpace N]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
  {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
  (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ)),
  ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e → ContDiff ℝ ∞ φ →
  ContMDiff … (fun p => TotalSpace.mk' … p (pullbackFlatFormFun e φ p))

## Strategic notes
Integration-current bridge, first brick: the pullback `e* φ` of a *flat* test `k`-form
`φ` on the ambient `F` along a smooth map `e : N → F` is a genuine smooth section of the
form bundle on the manifold-with-boundary `N`. (Once proved, `e* φ` is a `DiffForm`, so
classical Stokes on `N` applies to it — that is the keystone `∂[[e]] = [[∂e]]`.)

**Model closely on the boundary pullback** `contMDiff_pullbackBdryFun`
(`Library/Geometry/ManifoldBdry/PullbackFormContMDiff.lean`) — the structure is identical:
trivialization-read identity → fixed-basepoint coordinate formula is smooth →
`Trivialization.contMDiffAt_section_iff` + `congr_of_eventuallyEq`.

The ONE difference: the coordinate derivative here is the *varying*
`fderiv ℝ (e ∘ (extChartAt …).symm)` (the boundary case had the *constant* `faceEmbedL`).
Its fibrewise smoothness is the proved analytic core
`Library.Geometry.Manifold.AlternatingMapContDiff.contdiff_comp_continuous_linear_map_clm`
composed with `ContDiff.fderiv_right` (the coordinate derivative `x ↦ fderiv ℝ ê x` is
`C^∞` because `ê = e ∘ chart.symm` is). `e` and `φ` are given smooth — neither is
constructed; the work is the manifold-bundle assembly, not new analysis.

Helpers to mirror (boundary file): `pullback_triv_read_coord_change`,
`pullback_coord_rep_contmdiffon_target`, `pullback_fixed_chart_contmdiff_at`,
`pullback_coord_change_commute` (the coord-change naturality — for general `e` this is the
chain rule for `fderiv` under chart change, vs the face-sandwich identity in the boundary
case).
