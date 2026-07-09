import Library.Geometry.Currents.PullbackFormBounded         -- pullbackFlatForm_integral_bounded (crux)
import Library.Geometry.Currents.BoundarySquareZero          -- Current
import Library.Geometry.Manifold.StokesIntegralDefs          -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.PullbackFlatDNat        -- pullbackFlatForm
import Library.Geometry.Currents.DiffFormIntegralSmul
import Library.Geometry.Currents.PullbackFlatFormLinear
import Library.Geometry.Manifold.PerBumpStokes

/-!
# Integration current via pullback

This module constructs the **integration current** associated to a smooth map `e : N → F`
from an oriented compact manifold with boundary $N$ into a normed space $F$.

Given such a map, we define a de Rham current $T$ of degree $(n+1)$ on $F$ via
$T(\varphi) = \int_N e^*\varphi$. The main steps are:
1. Establish a seminorm bound for the per-compact integration functional.
2. Prove linearity (additivity and homogeneity) of that functional.
3. Package each per-compact piece as a continuous linear map.
4. Assemble the colimit to obtain a global current.

## Main statements

- `pullback_integral_seminorm_bound`: the functional `f ↦ ∫_N e^*(ofSupportedIn f)` satisfies
  a single-seminorm bound `|T f| ≤ C * N[ℝ]_{K,0} f`.
- `pullback_integral_add`: the per-compact integration functional is additive in `f`.
- `pullback_integral_smul`: the per-compact integration functional is $\mathbb{R}$-homogeneous.
- `pullback_integral_compact_clm_exists`: for each compact $K \subseteq F$, the integration
  functional extends to a continuous linear map on test forms supported in $K$.
- `exists_current_pullback_integral`: there exists a de Rham current `T` on `(⊤ : Opens F)`
  satisfying `T φ = DiffForm.integral (pullbackFlatForm e φ)` for all test forms `φ`.
-/

open Library.Geometry.Currents.BoundarySquareZero
open Library.Geometry.Currents.DiffFormIntegralSmul
open Library.Geometry.Currents.PullbackFlatFormLinear
open Library.Geometry.Currents.PullbackFormBounded
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.PullbackFlatDNat
open TopologicalSpace
open scoped Manifold Bundle ContDiff Distributions

namespace Library.Geometry.Currents.IntegrationCurrentCLM

/-- For a smooth map `e : N → F` and compact `K ⊆ F`, there exists a constant $C \geq 0$ such
that `|∫_N e^*(ofSupportedIn f)| ≤ C * N[ℝ]_{K,0} f` for all test forms `f`.
The global bound `C` is obtained from `pullbackFlatForm_integral_bounded`; the pointwise
estimate `‖f y‖ ≤ N[ℝ]_{K,0} f` is `ContDiffMapSupportedIn.norm_apply_le_seminorm`. -/
theorem pullback_integral_seminorm_bound {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e)
    (K : TopologicalSpace.Compacts F) (hK : (↑K : Set F) ⊆ (⊤ : Opens F)) :
    ∃ C : ℝ, 0 ≤ C ∧ ∀ (f : 𝓓^{(⊤ : ℕ∞)}_{K}(F, F [⋀^Fin (n + 1)]→L[ℝ] ℝ)),
      |DiffForm.integral (pullbackFlatForm e (⇑(TestFunction.ofSupportedIn hK f)) he
        (TestFunction.ofSupportedIn hK f).contDiff)| ≤ C * (N[ℝ]_{K, 0} f) := by
  obtain ⟨C, hC0, hC⟩ := pullbackFlatForm_integral_bounded e he
  refine ⟨C, hC0, fun f => hC _ _ (N[ℝ]_{K, 0} f) (fun y => ?_)⟩
  change ‖f y‖ ≤ _
  exact ContDiffMapSupportedIn.norm_apply_le_seminorm ℝ

/-- The per-compact pullback-integration functional `f ↦ ∫_N e^*(ofSupportedIn f)` is additive:
integrating the pullback of `f + g` equals the sum of the individual integrals. -/
theorem pullback_integral_add {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e)
    (K : TopologicalSpace.Compacts F) (hK : (↑K : Set F) ⊆ (⊤ : Opens F)) :
    ∀ (f g : 𝓓^{(⊤ : ℕ∞)}_{K}(F, F [⋀^Fin (n + 1)]→L[ℝ] ℝ)),
      DiffForm.integral (pullbackFlatForm e (⇑(TestFunction.ofSupportedIn hK (f + g))) he
        (TestFunction.ofSupportedIn hK (f + g)).contDiff)
      = DiffForm.integral (pullbackFlatForm e (⇑(TestFunction.ofSupportedIn hK f)) he
          (TestFunction.ofSupportedIn hK f).contDiff)
      + DiffForm.integral (pullbackFlatForm e (⇑(TestFunction.ofSupportedIn hK g)) he
          (TestFunction.ofSupportedIn hK g).contDiff) := by
  intro f g
  rw [pullback_flat_form_add e he K hK f g]
  exact Library.Geometry.Manifold.PerBumpStokes.diffform_integral_add _ _

/-- The per-compact pullback-integration functional `f ↦ ∫_N e^*(ofSupportedIn f)` is
$\mathbb{R}$-homogeneous: `∫_N e^*(ofSupportedIn (c • f)) = c • ∫_N e^*(ofSupportedIn f)`.
`pullback_flat_form_ofSupportedIn_smul` scales the pulled-back form, then
`diffform_integral_smul` pulls the scalar through `DiffForm.integral`. -/
theorem pullback_integral_smul {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e)
    (K : TopologicalSpace.Compacts F) (hK : (↑K : Set F) ⊆ (⊤ : Opens F)) :
    ∀ (c : ℝ) (f : 𝓓^{(⊤ : ℕ∞)}_{K}(F, F [⋀^Fin (n + 1)]→L[ℝ] ℝ)),
      DiffForm.integral (pullbackFlatForm e (⇑(TestFunction.ofSupportedIn hK (c • f))) he
        (TestFunction.ofSupportedIn hK (c • f)).contDiff)
      = c • DiffForm.integral (pullbackFlatForm e (⇑(TestFunction.ofSupportedIn hK f)) he
          (TestFunction.ofSupportedIn hK f).contDiff) := by
  intro c f
  rw [pullback_flat_form_ofSupportedIn_smul e he K hK c f, diffform_integral_smul]

/-- For a smooth map `e : N → F` and compact `K ⊆ F`, the per-compact pullback-integration
functional extends to a continuous linear map
`T_K : 𝓓^{⊤}_{K}(F, F [⋀^Fin (n+1)]→L[ℝ] ℝ) →L[ℝ] ℝ`
satisfying `T_K f = ∫_N e^*(ofSupportedIn f)` for all test forms `f`. -/
theorem pullback_integral_compact_clm_exists {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e)
    (K : TopologicalSpace.Compacts F) (hK : (↑K : Set F) ⊆ (⊤ : Opens F)) :
    ∃ T_K : 𝓓^{(⊤ : ℕ∞)}_{K}(F, F [⋀^Fin (n + 1)]→L[ℝ] ℝ) →L[ℝ] ℝ,
      ∀ f, T_K f = DiffForm.integral
        (pullbackFlatForm e (⇑(TestFunction.ofSupportedIn hK f)) he
          (TestFunction.ofSupportedIn hK f).contDiff) := by
  set tf : 𝓓^{(⊤ : ℕ∞)}_{K}(F, F [⋀^Fin (n + 1)]→L[ℝ] ℝ) → ℝ :=
    fun f => DiffForm.integral
      (pullbackFlatForm e (⇑(TestFunction.ofSupportedIn hK f)) he
        (TestFunction.ofSupportedIn hK f).contDiff)
  have hadd := pullback_integral_add e he K hK
  have hsmul := pullback_integral_smul e he K hK
  obtain ⟨C, hC0, hbound⟩ := pullback_integral_seminorm_bound e he K hK
  let L : 𝓓^{(⊤ : ℕ∞)}_{K}(F, F [⋀^Fin (n + 1)]→L[ℝ] ℝ) →ₗ[ℝ] ℝ :=
    { toFun := tf, map_add' := hadd, map_smul' := hsmul }
  have hcont : Continuous L := by
    refine WithSeminorms.continuous_of_isBounded (ContDiffMapSupportedIn.withSeminorms ..)
      (norm_withSeminorms ℝ ℝ) L (Seminorm.IsBounded.of_real (fun _ => ⟨{0}, C, fun f => ?_⟩))
    simp only [Finset.sup_singleton, coe_normSeminorm, Real.norm_eq_abs]
    exact hbound f
  exact ⟨⟨L, hcont⟩, fun f => rfl⟩

/-- **Integration current**: for every smooth map `e : N → F` from an oriented compact manifold
with boundary into a normed space, there exists a de Rham current
`T : Current (⊤ : Opens F) (n + 1)` satisfying
`T φ = DiffForm.integral (pullbackFlatForm e φ)` for all compactly supported test forms `φ`. -/
theorem exists_current_pullback_integral : ∀ {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e),
    ∃ (T : Current (⊤ : Opens F) (n + 1)),
      ∀ (φ : 𝓓^{(⊤ : ℕ∞)}((⊤ : Opens F), F [⋀^Fin (n + 1)]→L[ℝ] ℝ)),
        T φ = DiffForm.integral (pullbackFlatForm e (⇑φ) he φ.contDiff) := by
  intro n N _ _ _ _ _ _ F _ _ e he
  choose T_K hT_K using
    (fun (K : TopologicalSpace.Compacts F) (hK : (↑K : Set F) ⊆ (⊤ : Opens F)) =>
      pullback_integral_compact_clm_exists e he K hK)
  refine ⟨TestFunction.limitCLM ℝ
    (fun φ => DiffForm.integral (pullbackFlatForm e (⇑φ) he φ.contDiff)) T_K
    (fun K hK f => (hT_K K hK f).symm), ?_⟩
  intro φ
  rfl

end Library.Geometry.Currents.IntegrationCurrentCLM
