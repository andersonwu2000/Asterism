import Library.Geometry.Manifold.DDZero
import Library.Geometry.Manifold.DiffFormBundle
import Library.Geometry.ManifoldBdry.PullbackFlatForm
import Library.Geometry.ManifoldBdry.SectionEqOfCoord

/-!
# Flat pullback d-naturality on manifolds with boundary

This file proves that the exterior derivative commutes with the flat pullback of differential
forms on a manifold with boundary modelled on Euclidean half-space. Concretely, given a
smooth map `e : N → F` and a smooth form-valued function `φ : F → (F [⋀^Fin k]→L[ℝ] ℝ)`,
we have $d(e^*\varphi) = e^*(d\varphi)$ as an equality of `DiffForm`s on `N`.

## Main definitions

* `pullbackFlatForm`: the flat pullback `e^* φ` packaged as a `DiffForm` on `N`.

## Main statements

* `mextDeriv_pullbackFlatForm`: the manifold exterior derivative commutes with the flat
  pullback.
-/

open Bundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.ManifoldBdry.PullbackFlatForm
open Library.Geometry.ManifoldBdry.SectionEqOfCoord
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBdry.PullbackFlatDNat

variable {n k : ℕ}
  {N : Type*} [TopologicalSpace N]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
  {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]

/-- The flat pullback `e^* φ` packaged as a genuine smooth `k`-form on the
manifold-with-boundary `N`. The underlying section is `pullbackFlatFormFun e φ` and
smoothness is certified by `contMDiff_pullbackFlatFormFun`. -/
noncomputable def pullbackFlatForm (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hφ : ContDiff ℝ ∞ φ) :
    DiffForm (𝓡∂ (n + 1)) N k where
  toFun := pullbackFlatFormFun e φ
  contMDiff_toFun := contMDiff_pullbackFlatFormFun e φ he hφ

/-- Flat d-naturality of the pullback coordinate representative.

Setting `ê := e ∘ (extChartAt (𝓡∂ (n + 1)) x₀).symm`, the `extDerivWithin` within
`Set.range (𝓡∂ (n + 1))` of `z ↦ (φ (ê z)).compContinuousLinearMap (fderivWithin ℝ ê · z)`
at `y` equals `((extDeriv φ) (ê y)).compContinuousLinearMap (fderivWithin ℝ ê · y)`.
This is a direct application of `extDerivWithin_pullback`, with `extDerivWithin_univ`
converting `extDerivWithin φ univ` to `extDeriv φ`. -/
theorem ext_deriv_within_flat_pullback
    {n k : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hφ : ContDiff ℝ ∞ φ)
    (x₀ : N) (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hy : y ∈ (extChartAt (𝓡∂ (n + 1)) x₀).target) :
    extDerivWithin
        (fun z => (φ (e ((extChartAt (𝓡∂ (n + 1)) x₀).symm z))).compContinuousLinearMap
          (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x₀).symm)
            (Set.range (𝓡∂ (n + 1))) z))
        (Set.range (𝓡∂ (n + 1))) y
      = ((extDeriv φ) (e ((extChartAt (𝓡∂ (n + 1)) x₀).symm y))).compContinuousLinearMap
          (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x₀).symm)
            (Set.range (𝓡∂ (n + 1))) y)  := by
  rw [← extDerivWithin_univ φ]
  exact extDerivWithin_pullback
    ((hφ.differentiable (by norm_num)).differentiableAt.differentiableWithinAt)
    (((pullback_flat_chart_read_contdiffon e he x₀).contDiffWithinAt hy).mono_of_mem_nhdsWithin
      (extChartAt_target_mem_nhdsWithin_of_mem hy))
    (by norm_num [minSmoothness]; exact WithTop.coe_le_coe.mpr le_top)
    (𝓡∂ (n + 1)).uniqueDiffOn
    ((𝓡∂ (n + 1)).range_subset_closure_interior (extChartAt_target_subset_range x₀ hy))
    (extChartAt_target_subset_range x₀ hy)
    (Set.mapsTo_univ _ _)

/-- The `formInCoord` representative of the flat pullback `pullbackFlatForm e ψ` at
basepoint `x₀`, evaluated at `y`, equals
`(ψ (e ((extChartAt I x₀).symm y))).compContinuousLinearMap
(fderivWithin ℝ (e ∘ (extChartAt I x₀).symm) (Set.range I) y)`.

The proof unfolds `formInCoord` via `Trivialization.continuousLinearMapAt_apply_of_mem`
and then collapses the result using `pullback_flat_triv_read` and `extChartAt.right_inv`. -/
theorem coord_rep_pullback
    {n m : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (ψ : F → (F [⋀^Fin m]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hψ : ContDiff ℝ ∞ ψ)
    (x₀ : N) (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hy : y ∈ (extChartAt (𝓡∂ (n + 1)) x₀).target) :
    formInCoord (𝓡∂ (n + 1)) (pullbackFlatForm e ψ he hψ) x₀ y
      = (ψ (e ((extChartAt (𝓡∂ (n + 1)) x₀).symm y))).compContinuousLinearMap
          (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x₀).symm)
            (Set.range (𝓡∂ (n + 1))) y)  := by
  have hp_src : (extChartAt (𝓡∂ (n + 1)) x₀).symm y ∈
      (chartAt (EuclideanHalfSpace (n + 1)) x₀).source := by
    rw [← extChartAt_source (𝓡∂ (n + 1))]
    exact (extChartAt (𝓡∂ (n + 1)) x₀).map_target hy
  have h_y : extChartAt (𝓡∂ (n + 1)) x₀ ((extChartAt (𝓡∂ (n + 1)) x₀).symm y) = y :=
    (extChartAt (𝓡∂ (n + 1)) x₀).right_inv hy
  simp only [formInCoord]
  rw [Trivialization.continuousLinearMapAt_apply_of_mem ℝ _ hp_src]
  rw [show (pullbackFlatForm e ψ he hψ) ((extChartAt (𝓡∂ (n + 1)) x₀).symm y)
      = pullbackFlatFormFun e ψ ((extChartAt (𝓡∂ (n + 1)) x₀).symm y) from rfl]
  rw [pullback_flat_triv_read e ψ x₀ _ hp_src, h_y]

/-- The `formInCoord` representative of `pullbackFlatForm e φ` agrees pointwise with
`z ↦ (φ (e ((extChartAt I x₀).symm z))).compContinuousLinearMap (fderivWithin ℝ ê · z)`
on all of `(extChartAt I x₀).target`, where `ê = e ∘ (extChartAt I x₀).symm`. -/
theorem coord_rep_pullback_eqon
    {n k : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hφ : ContDiff ℝ ∞ φ)
    (x₀ : N) :
    Set.EqOn (formInCoord (𝓡∂ (n + 1)) (pullbackFlatForm e φ he hφ) x₀)
      (fun z => (φ (e ((extChartAt (𝓡∂ (n + 1)) x₀).symm z))).compContinuousLinearMap
          (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x₀).symm)
            (Set.range (𝓡∂ (n + 1))) z))
      (extChartAt (𝓡∂ (n + 1)) x₀).target  := by
  intro z hz
  set p := (extChartAt (𝓡∂ (n + 1)) x₀).symm z with hp
  have hp_src : p ∈ (chartAt (EuclideanHalfSpace (n + 1)) x₀).source := by
    have h := (extChartAt (𝓡∂ (n + 1)) x₀).map_target hz
    rwa [extChartAt_source] at h
  have hz_eq : extChartAt (𝓡∂ (n + 1)) x₀ p = z :=
    (extChartAt (𝓡∂ (n + 1)) x₀).right_inv hz
  simp only [formInCoord]
  have hcoe : ⇑(pullbackFlatForm e φ he hφ) p = pullbackFlatFormFun e φ p := rfl
  rw [hcoe, Trivialization.continuousLinearMapAt_apply_of_mem ℝ _ hp_src,
    pullback_flat_triv_read e φ x₀ p hp_src, hz_eq]

/-- The coordinate representative of `pullbackFlatForm e φ` is eventually equal within
`𝓝[Set.range (𝓡∂ (n + 1))] y` to the flat pullback formula
`z ↦ (φ (ê z)).compContinuousLinearMap (fderivWithin ℝ ê (Set.range I) z)`.

This lifts `coord_rep_pullback_eqon` from a pointwise `Set.EqOn` on the chart target to a
filter `Filter.EventuallyEq`, using `extChartAt_target_mem_nhdsWithin_of_mem`. -/
theorem coord_rep_pullback_eventually_eq
    {n k : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hφ : ContDiff ℝ ∞ φ)
    (x₀ : N) (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hy : y ∈ (extChartAt (𝓡∂ (n + 1)) x₀).target) :
    formInCoord (𝓡∂ (n + 1)) (pullbackFlatForm e φ he hφ) x₀
      =ᶠ[nhdsWithin y (Set.range (𝓡∂ (n + 1)))]
      (fun z => (φ (e ((extChartAt (𝓡∂ (n + 1)) x₀).symm z))).compContinuousLinearMap
          (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x₀).symm)
            (Set.range (𝓡∂ (n + 1))) z))  := by
  have h_eqon := coord_rep_pullback_eqon e φ he hφ x₀
  exact Filter.eventuallyEq_of_mem (extChartAt_target_mem_nhdsWithin_of_mem hy) h_eqon

/-- The coordinate representative of `mextDeriv I (pullbackFlatForm e φ)` at `(x₀, y)`
equals `((extDeriv φ) (ê y)).compContinuousLinearMap (fderivWithin ℝ ê (Set.range I) y)`,
where `ê = e ∘ (extChartAt I x₀).symm`.

The proof chain: `form_in_coord_mext_deriv_eq` collapses `mextDeriv` to `extDerivWithin` of
the coordinate representative; `coord_rep_pullback_eventually_eq` rewrites that representative
near `y`; and `ext_deriv_within_flat_pullback` supplies the flat d-naturality identity. -/
theorem coord_rep_mext_pullback
    {n k : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hφ : ContDiff ℝ ∞ φ)
    (x₀ : N) (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hy : y ∈ (extChartAt (𝓡∂ (n + 1)) x₀).target) :
    formInCoord (𝓡∂ (n + 1)) (mextDeriv (𝓡∂ (n + 1)) (pullbackFlatForm e φ he hφ)) x₀ y
      = ((extDeriv φ) (e ((extChartAt (𝓡∂ (n + 1)) x₀).symm y))).compContinuousLinearMap
          (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) x₀).symm)
            (Set.range (𝓡∂ (n + 1))) y)  := by
  have hy_range : y ∈ Set.range (𝓡∂ (n + 1)) := extChartAt_target_subset_range x₀ hy
  have h_coord_rep := coord_rep_pullback_eventually_eq e φ he hφ x₀ y hy
  have h_ext_deriv := ext_deriv_within_flat_pullback e φ he hφ x₀ y hy
  rw [form_in_coord_mext_deriv_eq (𝓡∂ (n + 1)) (pullbackFlatForm e φ he hφ) x₀ y hy,
      h_coord_rep.extDerivWithin_eq_of_mem hy_range]
  exact h_ext_deriv

/-- **d-naturality of the flat pullback**: the manifold exterior derivative commutes with the
flat pullback along a smooth map.

For `e : N → F` smooth and `φ : F → (F [⋀^Fin k]→L[ℝ] ℝ)` smooth with smooth exterior
derivative `extDeriv φ`, the equality
`mextDeriv (𝓡∂ (n + 1)) (pullbackFlatForm e φ he hφ) = pullbackFlatForm e (extDeriv φ) he hdφ`
holds as smooth `(k+1)`-forms on `N`. The proof uses `section_eq_of_coord`: two `DiffForm`s
agree iff all their chart coordinate representatives agree, which is checked via
`coord_rep_mext_pullback` and `coord_rep_pullback`. -/
theorem mextDeriv_pullbackFlatForm : ∀ {n k : ℕ} {N : Type*} [TopologicalSpace N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hφ : ContDiff ℝ ∞ φ)
    (hdφ : ContDiff ℝ ∞ (extDeriv φ)),
    mextDeriv (𝓡∂ (n + 1)) (pullbackFlatForm e φ he hφ)
      = pullbackFlatForm e (extDeriv φ) he hdφ  := by
  intro n k N _ _ _ F _ _ e φ he hφ hdφ
  apply section_eq_of_coord
  intro x₀ y hy
  rw [coord_rep_mext_pullback e φ he hφ x₀ y hy]
  exact (coord_rep_pullback e (extDeriv φ) he hdφ x₀ y hy).symm

end Library.Geometry.ManifoldBdry.PullbackFlatDNat
