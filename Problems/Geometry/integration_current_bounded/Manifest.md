---
problem: Geometry.integration_current_bounded
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# Geometry.integration_current_bounded — C⁰ boundedness of the integration current (LF-continuity crux)

## Statement
∀ {n : ℕ} {N : Type*} [compact oriented manifold-with-boundary on EuclideanHalfSpace (n+1)]
  {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
  (e : N → F) (he : ContMDiff … ∞ e),
  ∃ C ≥ 0, ∀ (ψ : F → (F [⋀^Fin (n+1)]→L[ℝ] ℝ)) (hψ : ContDiff ℝ ∞ ψ) (M : ℝ),
    (∀ y, ‖ψ y‖ ≤ M) → |DiffForm.integral (pullbackFlatForm e ψ he hψ)| ≤ C * M

## Strategic notes
**Final analytic brick of the de Rham currents bridge.** This is the one genuinely-new
estimate (no existing bound on `DiffForm.integral` / `localCoeff` in Library or Mathlib).
Once proven, it upgrades the integration current `[[e]] : ψ ↦ ∫_N e* ψ` to a continuous
`Library.Geometry.Currents.…Current` via `TestFunction.continuous_of_isBounded` (per-compact
seminorm bound) + `limitCLM`. NOT a leaf-bypass — expect a multi-node analytic decomposition.

**Proof roadmap** (`DiffForm.integral` = a finite partition-of-unity sum of chart integrals):
1. **Coordinate-coefficient bound** (the crux node): the coordinate coefficient of the flat
   pullback is bounded by `M` times a fderiv factor. `localCoeff (pullbackFlatForm e ψ) x y
   = topCoeff (formInCoord … x y)`, and `formInCoord` of the flat pullback at `y` is
   `(ψ (e (chart.symm y))).compContinuousLinearMap (fderivWithin ℝ (e ∘ chart.symm) (range 𝓡∂) y)`.
   So `|localCoeff …| ≤ ‖ψ (e (chart.symm y))‖ · ‖fderivWithin …‖ ^ (n+1) ≤ M · D`, where
   `D` bounds the chart-derivative of `e` over the (compact, via POU support) region —
   `e` is `ContMDiff` and `N` compact, so `‖fderivWithin (e ∘ chart.symm)‖` is bounded.
   `topCoeff α = α (EuclideanSpace.basisFun …)` ≤ `‖α‖ · ‖basisFun‖`.
2. **Per-chart integral bound**: `|∫ POUᵢ · localCoeff · sign| ≤ ∫ POUᵢ · (M·D) ≤ M·D·volume(target)`;
   the chart target has finite `volume` (compact manifold), `POUᵢ ∈ [0,1]`, `|sign| ≤ 1`.
3. **Finite-sum bound**: the partition of unity is subordinate to a finite cover of compact
   `N` ⇒ the `∑ᶠ` is a finite sum of bounded terms ⇒ `≤ M · (D · ∑ volume) = M · C`.
4. The witness `C` is `D · (∑ over the cover charts of their target volume)` — both finite,
   `≥ 0`. The cover is the one chosen inside `DiffForm.integral`; unfold to reach it.

Chart machinery (chart change / `localCoeff` identities / oriented density) is in
`Library/Geometry/Manifold/{LocalCoeffDensity,LocalCoeffCoordChange,MExtDerivCoord}.lean`;
the pullback coordinate representative + chart-independence is the harvested
`Library.Geometry.ManifoldBdry.PullbackFlatDNat` (`pullbackFlatForm`,
`fderivWithin_comp_coordChange_eq`). Boundedness of a continuous function on a compact set
and finiteness of `volume` on compacts are Mathlib.
