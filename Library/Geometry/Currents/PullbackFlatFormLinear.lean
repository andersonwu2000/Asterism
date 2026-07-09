import Library.Geometry.Currents.PullbackFormBounded         -- pullbackFlatForm_integral_bounded (crux)
import Library.Geometry.Currents.BoundarySquareZero          -- Current
import Library.Geometry.Manifold.StokesIntegralDefs          -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.PullbackFlatDNat        -- pullbackFlatForm

/-!
# Linearity of `pullbackFlatForm` in the test form

This file proves that `pullbackFlatForm` is additive and scalar-homogeneous in its
test-form argument, both for general smooth coefficient maps and for compactly-supported
test forms embedded via `TestFunction.ofSupportedIn`.

## Main statements

- `pullback_flat_form_general_add`: `pullbackFlatForm e (ψ₁ + ψ₂)` equals the sum of
  the individual pullbacks.
- `pullback_flat_form_add`: additivity over `ofSupportedIn`-embedded test forms.
- `ofSupportedIn_coe_smul`: the coercion `⇑(ofSupportedIn hK (c • f))` equals
  `c • ⇑(ofSupportedIn hK f)`.
- `pullback_flat_form_general_smul`: `pullbackFlatForm e (c • ψ)` equals
  `c • pullbackFlatForm e ψ`.
- `pullback_flat_form_ofSupportedIn_smul`: scalar homogeneity over `ofSupportedIn`
  test forms.
-/

open Library.Geometry.Currents.BoundarySquareZero
open Library.Geometry.Currents.PullbackFormBounded
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.PullbackFlatDNat
open TopologicalSpace
open scoped Manifold Bundle ContDiff Distributions

namespace Library.Geometry.Currents.PullbackFlatFormLinear

/-- `pullbackFlatForm` is additive in its test-form argument: if $\psi_1$ and $\psi_2$
are smooth, then $e^*(\psi_1 + \psi_2) = e^*\psi_1 + e^*\psi_2$.

The proof unfolds to the fibrewise level via `pullbackFlatFormFun` and uses
`Trivialization.symmL`'s linearity (`map_add`) together with `compContinuousLinearMapₗ`
to reduce to `congr 1`. -/
theorem pullback_flat_form_general_add {n k : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e)
    (ψ₁ ψ₂ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (hψ₁ : ContDiff ℝ ∞ ψ₁) (hψ₂ : ContDiff ℝ ∞ ψ₂) (hψ : ContDiff ℝ ∞ (ψ₁ + ψ₂)) :
    Library.Geometry.ManifoldBdry.PullbackFlatDNat.pullbackFlatForm e (ψ₁ + ψ₂) he hψ =
      Library.Geometry.ManifoldBdry.PullbackFlatDNat.pullbackFlatForm e ψ₁ he hψ₁ +
        Library.Geometry.ManifoldBdry.PullbackFlatDNat.pullbackFlatForm e ψ₂ he hψ₂ := by
  apply ContMDiffSection.ext
  intro p
  change Library.Geometry.ManifoldBdry.PullbackFlatForm.pullbackFlatFormFun e (ψ₁ + ψ₂) p =
    Library.Geometry.ManifoldBdry.PullbackFlatForm.pullbackFlatFormFun e ψ₁ p +
    Library.Geometry.ManifoldBdry.PullbackFlatForm.pullbackFlatFormFun e ψ₂ p
  unfold Library.Geometry.ManifoldBdry.PullbackFlatForm.pullbackFlatFormFun
  rw [Pi.add_apply]
  rw [← (Bundle.Trivialization.symmL ℝ
      (trivializationAt (EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ)
        (Library.Geometry.Manifold.DiffFormBundle.formBundleCore (𝓡∂ n + 1) k).Fiber p) p).map_add]
  congr 1

/-- Additivity of `pullbackFlatForm` over `ofSupportedIn`-embedded compactly-supported
test forms: if $f$ and $g$ are supported in $K$, then $e^*(f + g) = e^*f + e^*g$.

The `ofSupportedIn` coercion is definitionally additive, so `⇑(ofSupportedIn (f + g))`
is defeq to the pointwise sum; `pullback_flat_form_general_add` then closes the goal
(contDiff certificates are proof-irrelevant for the underlying section). -/
theorem pullback_flat_form_add {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e)
    (K : TopologicalSpace.Compacts F) (hK : (↑K : Set F) ⊆ (⊤ : Opens F))
    (f g : 𝓓^{(⊤ : ℕ∞)}_{K}(F, F [⋀^Fin (n + 1)]→L[ℝ] ℝ)) :
    pullbackFlatForm e (⇑(TestFunction.ofSupportedIn hK (f + g))) he
        (TestFunction.ofSupportedIn hK (f + g)).contDiff
      = pullbackFlatForm e (⇑(TestFunction.ofSupportedIn hK f)) he
          (TestFunction.ofSupportedIn hK f).contDiff
        + pullbackFlatForm e (⇑(TestFunction.ofSupportedIn hK g)) he
            (TestFunction.ofSupportedIn hK g).contDiff := by
  exact pullback_flat_form_general_add e he
    (⇑(TestFunction.ofSupportedIn hK f)) (⇑(TestFunction.ofSupportedIn hK g))
    (TestFunction.ofSupportedIn hK f).contDiff (TestFunction.ofSupportedIn hK g).contDiff
    (TestFunction.ofSupportedIn hK (f + g)).contDiff

/-- The coercion `⇑(ofSupportedIn hK (c • f))` equals `c • ⇑(ofSupportedIn hK f)` as a
function $F \to F [⋀^{\mathrm{Fin}(n+1)}]→_ℝ ℝ$. -/
theorem ofSupportedIn_coe_smul {n : ℕ} {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    {K : TopologicalSpace.Compacts F} (hK : (↑K : Set F) ⊆ (⊤ : TopologicalSpace.Opens F))
    (c : ℝ) (f : ContDiffMapSupportedIn F (F [⋀^Fin (n + 1)]→L[ℝ] ℝ) (⊤ : ℕ∞) K) :
    (⇑(TestFunction.ofSupportedIn hK (c • f)) : F → (F [⋀^Fin (n + 1)]→L[ℝ] ℝ))
      = c • ⇑(TestFunction.ofSupportedIn hK f) := by norm_num

/-- Scalar homogeneity of `pullbackFlatForm` in the test form: if $\psi' = c \cdot \psi$,
then $e^*\psi' = c \cdot e^*\psi$.

The proof uses `DiffForm.ext` to reduce to the fibrewise equality, then applies
`ContinuousAlternatingMap.compContinuousLinearMap` linearity and `symmL`'s `map_smul`. -/
theorem pullback_flat_form_general_smul {n k : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e)
    (c : ℝ) (ψ' ψ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (hψ' : ContDiff ℝ ∞ ψ') (hψ : ContDiff ℝ ∞ ψ) (heq : ψ' = c • ψ) :
    pullbackFlatForm e ψ' he hψ' = c • pullbackFlatForm e ψ he hψ := by
  subst heq
  ext p
  simp only [ContMDiffSection.coe_smul, Pi.smul_apply]
  change Library.Geometry.ManifoldBdry.PullbackFlatForm.pullbackFlatFormFun e (c • ψ) p =
    c • Library.Geometry.ManifoldBdry.PullbackFlatForm.pullbackFlatFormFun e ψ p
  simp only [Library.Geometry.ManifoldBdry.PullbackFlatForm.pullbackFlatFormFun, Pi.smul_apply]
  let L := fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p).symm)
    (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p p)
  have key : (c • ψ (e p)).compContinuousLinearMap L =
      c • (ψ (e p)).compContinuousLinearMap L := by
    ext v
    simp [ContinuousAlternatingMap.compContinuousLinearMap_apply]
  rw [key]
  exact (Bundle.Trivialization.symmL ℝ
    (trivializationAt (EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ)
      (Library.Geometry.Manifold.DiffFormBundle.formBundleCore (𝓡∂ (n + 1)) k).Fiber p)
    p).map_smul c ((ψ (e p)).compContinuousLinearMap L)

/-- Scalar homogeneity of `pullbackFlatForm` over `ofSupportedIn`-embedded test forms:
$e^*(c \cdot f) = c \cdot e^*f$.

Uses `ofSupportedIn_coe_smul` to rewrite `⇑(ofSupportedIn hK (c • f))` as
`c • ⇑(ofSupportedIn hK f)`, then applies `pullback_flat_form_general_smul`. -/
theorem pullback_flat_form_ofSupportedIn_smul {n : ℕ} {N : Type*} [TopologicalSpace N]
    [T2Space N] [ChartedSpace (EuclideanHalfSpace (n + 1)) N]
    [IsManifold (modelWithCornersEuclideanHalfSpace (n + 1)) ((⊤ : ℕ∞) : WithTop ℕ∞) N]
    [OrientedManifold (modelWithCornersEuclideanHalfSpace (n + 1)) N] [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F)
    (he : ContMDiff (modelWithCornersEuclideanHalfSpace (n + 1)) (modelWithCornersSelf ℝ F)
      ((⊤ : ℕ∞) : WithTop ℕ∞) e)
    (K : TopologicalSpace.Compacts F) (hK : (↑K : Set F) ⊆ (⊤ : TopologicalSpace.Opens F))
    (c : ℝ)
    (f : ContDiffMapSupportedIn F (F [⋀^Fin (n + 1)]→L[ℝ] ℝ) (⊤ : ℕ∞) K) :
    Library.Geometry.ManifoldBdry.PullbackFlatDNat.pullbackFlatForm e
        (⇑(TestFunction.ofSupportedIn hK (c • f))) he
        (TestFunction.ofSupportedIn hK (c • f)).contDiff
      = c • Library.Geometry.ManifoldBdry.PullbackFlatDNat.pullbackFlatForm e
          (⇑(TestFunction.ofSupportedIn hK f)) he
          (TestFunction.ofSupportedIn hK f).contDiff := by
  have h_coe : (⇑(TestFunction.ofSupportedIn hK (c • f)) : F → (F [⋀^Fin (n + 1)]→L[ℝ] ℝ))
      = c • ⇑(TestFunction.ofSupportedIn hK f) := ofSupportedIn_coe_smul hK c f
  exact pullback_flat_form_general_smul e he c _ _ _ _ h_coe

end Library.Geometry.Currents.PullbackFlatFormLinear
