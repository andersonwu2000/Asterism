---
problem: Geometry.pullback_flat_dnat
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# Geometry.pullback_flat_dnat — d-naturality of the flat pullback

## Statement
∀ {n k : ℕ} {N : Type*} [TopologicalSpace N]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
  {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
  (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
  (he : ContMDiff … ∞ e) (hφ : ContDiff ℝ ∞ φ) (hdφ : ContDiff ℝ ∞ (extDeriv φ)),
  mextDeriv (𝓡∂ (n + 1)) (pullbackFlatForm e φ he hφ) = pullbackFlatForm e (extDeriv φ) he hdφ

## Strategic notes
Integration-current bridge, **d-step (brick ②)**. Brick ① is done and harvested
(`Library.Geometry.ManifoldBdry.PullbackFlatForm`): `e* φ` is a smooth `DiffForm`. This
brick proves the manifold exterior derivative commutes with that pullback —
`d(e* φ) = e* (dφ)` — which, fed into classical Stokes on `N` (keystone
`Problems/Geometry/stokes_theorem` `s17649`: `∫_M dψ = ∫_∂M ψ|_∂`), gives `∂[[e]] = [[∂e]]`.

This is a **DiffForm (section) equality**. Two sections are equal iff they agree fibrewise,
which reduces to equality of their coordinate representatives `formInCoord … x₀ y` on each
chart target. The proof chains three facts; there is **no existing manifold-level
d-naturality lemma** — this is the first.

1. **Reduce to coordinates** — `formInCoord` of `mextDeriv φ` is the flat `extDerivWithin`
   of `formInCoord φ`: `Library.Geometry.Manifold.DDZero.form_in_coord_mext_deriv_eq`
   (`formInCoord I (mextDeriv I φ) x₀ y = extDerivWithin (formInCoord I φ x₀) (Set.range I) y`
   on `(extChartAt I x₀).target`).
2. **Flat d-naturality** — the coordinate representative of `pullbackFlatForm e φ` at `x₀`
   has the shape `fun y => (φ (ê y)).compContinuousLinearMap (fderivWithin ℝ ê (Set.range 𝓡∂) y)`
   with `ê = e ∘ (extChartAt 𝓡∂ x₀).symm`. Apply Mathlib `extDerivWithin_pullback`
   (`Mathlib/Analysis/Calculus/DifferentialForm/Basic.lean`,
   `extDerivWithin (fun y => (ω (f y)).compContinuousLinearMap (fderivWithin 𝕜 f s y)) s x
   = (extDerivWithin ω t (f x)).compContinuousLinearMap (fderivWithin 𝕜 f s x)`) with
   `ω := φ`, `f := ê`, `s := Set.range 𝓡∂`. Side conditions: `UniqueDiffOn ℝ (Set.range (𝓡∂ (n+1)))`
   (model-with-corners range), `x ∈ closure (interior (range 𝓡∂))`, `minSmoothness ℝ 2 ≤ ∞`,
   `MapsTo ê (range 𝓡∂) univ`. Since `φ` is global, `extDerivWithin φ univ = extDeriv φ`.
3. **Match the RHS coordinate representative** — `(extDeriv φ (ê y)).compContinuousLinearMap
   (fderivWithin ℝ ê (range 𝓡∂) y)` is exactly `formInCoord (pullbackFlatForm e (extDeriv φ)) x₀ y`.

Chart-independence of the coordinate representative (the basepoint `x₀` vs the per-point
chart in `pullbackFlatFormFun`) is the harvested
`Library.Geometry.ManifoldBdry.PullbackFlatForm.fderivWithin_comp_coordChange_eq`.

Key citations: `form_in_coord_mext_deriv_eq` (DDZero), `extDerivWithin_pullback` /
`extDeriv_pullback` (Mathlib), brick ① `pullbackFlatFormFun` / `contMDiff_pullbackFlatFormFun`
/ `fderivWithin_comp_coordChange_eq` (PullbackFlatForm). The `formInCoord` /
`trivialization`-read plumbing mirrors `Library/Geometry/ManifoldBdry/PullbackFormContMDiff.lean`.
