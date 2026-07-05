---
problem: Geometry.integration_current_clm
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# Geometry.integration_current_clm — integration current `[[e]]` is a genuine continuous `Current` (bridge capstone)

## Statement
∀ {n : ℕ} {N : Type*} [compact oriented manifold-with-boundary on EuclideanHalfSpace (n+1)]
  {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
  (e : N → F) (he : ContMDiff … ∞ e),
  ∃ (T : Current (⊤ : Opens F) (n+1)),
    ∀ (φ : 𝓓^{(⊤:ℕ∞)}((⊤ : Opens F), F [⋀^Fin (n+1)]→L[ℝ] ℝ)),
      T φ = DiffForm.integral (pullbackFlatForm e ⇑φ he φ.contDiff)

## Strategic notes
**Final brick — completes the de Rham integration-current bridge.** The analytic crux is
already proved and harvested (`Library.Geometry.Currents.PullbackFormBounded.pullbackFlatForm_integral_bounded`:
`∃ C ≥ 0, ∀ ψ (hψ) M, (∀ y, ‖ψ y‖ ≤ M) → |DiffForm.integral (pullbackFlatForm e ψ he hψ)| ≤ C·M`).
This brick is **API plumbing only** — no new analysis — turning that bound into a genuine
continuous functional via the LF-topology universal property.

**Proof roadmap:**
1. **Define the candidate functional** `toFun φ := DiffForm.integral (pullbackFlatForm e ⇑φ he φ.contDiff)`
   (`φ.contDiff : ContDiff ℝ ∞ ⇑φ` is `TestFunction.contDiff`; `⇑φ` is the test-form coercion).
2. **Per-compact CLM** — for each `K : Compacts F` with `K ⊆ ⊤`, build
   `T_K : 𝓓^{(⊤:ℕ∞)}_K(F, …) →L[ℝ] ℝ` via `TestFunction`/`ContDiffMapSupportedIn.continuous_of_isBounded`:
   the seminorm `N[ℝ]_{K,⊤,0} f = sup_{y∈K} ‖f y‖`, and the harvested bound gives
   `|toFun f| ≤ C · N[ℝ]_{K,⊤,0} f` (apply `pullbackFlatForm_integral_bounded` with `M := sup_K ‖⇑f‖`,
   finite since `f` is compactly supported in `K`: `Continuous.bounded_above_of_compact_support`).
3. **Glue** with `TestFunction.limitCLM toFun T_K (agreement)` — the agreement
   `toFun (ofSupportedIn h f) = T_K f` is definitional once `T_K`'s `toFun` is `toFun ∘ ofSupportedIn`.
4. **Witness** `T := limitCLM …`; the `∀ φ, T φ = toFun φ` clause is exactly `limitCLM`'s
   agreement extended over the LF colimit (or holds definitionally on the coercion).

Citations: `pullbackFlatForm_integral_bounded` (crux, Library), `Current` /
`BoundarySquareZero` (Library), `pullbackFlatForm` (`PullbackFlatDNat`, Library),
`TestFunction.limitCLM` / `.contDiff` / `continuous_of_isBounded` /
`ContDiffMapSupportedIn.seminorm` (Mathlib `Analysis/Distribution/`),
`Continuous.bounded_above_of_compact_support` (Mathlib).

The trickiest connection (Explore-flagged): the bound is global-`M`, `continuous_of_isBounded`
wants a per-`K` seminorm bound — bridged by `M := sup over K of ‖⇑f‖ = N[ℝ]_{K,⊤,0} f`, finite by
compact support. Standard, all pieces in Mathlib.
