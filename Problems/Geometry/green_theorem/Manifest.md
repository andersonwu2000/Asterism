---
problem: Geometry.green_theorem
library: false
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas:
  - "*integral2_divergence_prod*"
  - "*integral_divergence_of_hasFDerivAt*"
---

# Geometry.green_theorem — Green's theorem on the closed unit disk, via Stokes

## Statement
For smooth `P, Q : EuclideanSpace ℝ (Fin 2) → ℝ`, the counterclockwise boundary
line integral of the 1-form `P dx + Q dy` over the unit circle equals the double
integral of the scalar curl `∂Q/∂x − ∂P/∂y` over the closed unit disk:

`lineIntegral P Q = doubleIntegral P Q`

where `lineIntegral`/`doubleIntegral` (see `Defs.lean`) are the classical
`∮_∂D (P dx + Q dy)` and `∬_D (∂Q/∂x − ∂P/∂y)`. This is Green's theorem — the
`n = 1` case of the general Stokes theorem.

## Setting
**Prove via the abstract Stokes theorem already in the Library, NOT via Mathlib's
classical divergence theorem** (the `integral2_divergence_prod*` /
`integral_divergence_of_hasFDerivAt*` families are forbidden). The point is to
descend from the proved abstract manifold Stokes to a concrete classical identity
— building the classical↔manifold bridge that the Library does not yet have.

This is the first capstone of a **concrete-Stokes tower**. The foundational
bricks below (especially step 1) do not exist in Mathlib or the Library and must
be built; they are shared with higher-dimensional concrete Stokes, so proving
them as their own sub-goals/Library pieces first is expected and encouraged.

## Strategic notes
The bridge from the abstract keystone
`Library.Geometry.Manifold.PerBumpStokes.integral_mextDeriv_eq_integral_pullbackBdry`
(`∫_M dω = ∫_∂M ω` for a compact oriented manifold-with-boundary `M`, top-degree
form `ω`) down to the classical disk identity decomposes as:

1. **Concrete 2D region as a manifold-with-boundary.** Exhibit the closed unit
   disk `Metric.closedBall (0 : EuclideanSpace ℝ (Fin 2)) 1` as a compact oriented
   smooth manifold-with-boundary modelled on `EuclideanHalfSpace 2`:
   `ChartedSpace (EuclideanHalfSpace 2)` + `IsManifold (𝓡∂ 2) ∞` +
   `OrientedManifold (𝓡∂ 2)` + `CompactSpace` + `T2Space`. Mathlib provides NO 2D
   boundary-manifold instance (only `Icc 0 1` at `n = 1`, in
   `Mathlib/Geometry/Manifold/Instances/Real.lean` — use as a template for the
   atlas pattern). This atlas (interior chart + boundary collar charts + smooth
   transitions) is the foundational sub-tower; build and harvest it first.
2. **The 1-form.** Build `P dx + Q dy` as a `DiffForm (𝓡∂ 2) (disk) 1`.
3. **Apply the keystone.** `DiffForm.integral (mextDeriv (P dx + Q dy)) =
   DiffForm.integral (pullbackBdry (P dx + Q dy))`.
4. **LHS = doubleIntegral.** Compute `mextDeriv (P dx + Q dy)` in coordinates
   (`= (∂Q/∂x − ∂P/∂y) dx ∧ dy`), then collapse `DiffForm.integral` (a
   partition-of-unity sum) to a single chart via
   `Library.Geometry.Manifold.SingleChartCollapse.integral_single_chart_collapse`,
   matching the Lebesgue double integral over `closedBall 0 1`.
5. **RHS = lineIntegral.** `pullbackBdry` on the boundary circle, parametrized by
   `circle θ = !₂[cos θ, sin θ]`, is the classical line integral on `[0, 2π]`.

## Lemma hints
- `Library.Geometry.Manifold.PerBumpStokes.integral_mextDeriv_eq_integral_pullbackBdry`
- `Library.Geometry.Manifold.PerBumpStokes.pullbackBdry`
- `Library.Geometry.Manifold.DDZero.mextDeriv`
- `Library.Geometry.Manifold.StokesIntegralDefs.DiffForm.integral`
- `Library.Geometry.Manifold.StokesIntegralDefs.localCoeff`
- `Library.Geometry.Manifold.SingleChartCollapse.integral_single_chart_collapse`
- `Library.Geometry.Manifold.DiffFormBundle.DiffForm`
- `Library.Geometry.ManifoldBoundary.CompactBdry.compactSpace_bdry`
- `Library.Geometry.Manifold.PerBumpStokes.instBdryOriented`
