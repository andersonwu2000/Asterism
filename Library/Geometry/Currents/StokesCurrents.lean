import Library.Geometry.Manifold.PerBumpStokes                -- pullbackBdry, integral_mextDeriv_eq_integral_pullbackBdry (Stokes)
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.ManifoldBdry.PullbackFlatDNat         -- pullbackFlatForm, mextDeriv_pullbackFlatForm (brick ②)

/-!
# Stokes currents

Integration currents and their boundary identity for smooth maps into a normed space,
on a compact oriented manifold-with-boundary modelled on `EuclideanHalfSpace (n + 1)`.

## Main definitions

- `integrationCurrent`: the integration current `[[e]](w) = ∫_N e* w` for a smooth map
  `e : N → F` evaluated at a top-degree flat test form `w`.
- `boundaryIntegrationCurrent`: the boundary integration current
  `[[∂e]](ψ) = ∫_{∂N} (e|_{∂N})* ψ` evaluated at a flat `n`-form `ψ`.

## Main statements

- `integrationCurrent_extDeriv_eq_boundaryIntegrationCurrent`: the currents boundary identity
  `[[e]](dψ) = [[∂e]](ψ)`, i.e. `∂[[e]] = [[∂e]]` on flat test forms.
-/

open Bundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.PerBumpStokes
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.PullbackFlatDNat
open Library.Geometry.ManifoldBoundary.CompactBdry
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Currents.StokesCurrents

variable {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
  [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
  [T2Space (Bdry n N)] [CompactSpace (Bdry n N)]
  {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]

/-- Integration current `[[e]]` of a smooth `e : N → F` over the compact oriented
manifold-with-boundary `N`, at a top-degree flat test form `w`: `[[e]](w) = ∫_N e* w`. -/
noncomputable def integrationCurrent (e : N → F) (w : F → (F [⋀^Fin (n + 1)]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hw : ContDiff ℝ ∞ w) : ℝ :=
  DiffForm.integral (pullbackFlatForm e w he hw)

/-- Boundary integration current `[[∂e]]` at a flat test `n`-form `ψ`:
`[[∂e]](ψ) = ∫_{∂N} (e* ψ)|_{∂N}`. -/
noncomputable def boundaryIntegrationCurrent (e : N → F) (ψ : F → (F [⋀^Fin n]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hψ : ContDiff ℝ ∞ ψ) : ℝ :=
  DiffForm.integral (pullbackBdry (pullbackFlatForm e ψ he hψ))

/-- **Currents boundary identity**: for a smooth map `e : N → F` and a smooth flat `n`-form
family `ψ : F → F [⋀^Fin n]→L[ℝ] ℝ`, the integration current satisfies
`[[e]](dψ) = [[∂e]](ψ)`, i.e. `∂[[e]] = [[∂e]]` on flat test forms.

Proved by unfolding both sides to `DiffForm.integral`, rewriting via the d-naturality of the
flat pullback (`mextDeriv_pullbackFlatForm`), then applying the per-bump Stokes identity
`integral_mextDeriv_eq_integral_pullbackBdry`. -/
theorem integrationCurrent_extDeriv_eq_boundaryIntegrationCurrent :
    ∀ {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [OrientedManifold (𝓡∂ (n + 1)) N] [CompactSpace N]
    [T2Space (Bdry n N)] [CompactSpace (Bdry n N)]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (ψ : F → (F [⋀^Fin n]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hψ : ContDiff ℝ ∞ ψ)
    (hdψ : ContDiff ℝ ∞ (extDeriv ψ)),
    integrationCurrent e (extDeriv ψ) he hdψ = boundaryIntegrationCurrent e ψ he hψ := by
  intro n N _ _ _ _ _ _ _ _ F _ _ e ψ he hψ hdψ
  simp only [integrationCurrent, boundaryIntegrationCurrent]
  rw [← mextDeriv_pullbackFlatForm e ψ he hψ hdψ]
  exact integral_mextDeriv_eq_integral_pullbackBdry (pullbackFlatForm e ψ he hψ)

end Library.Geometry.Currents.StokesCurrents
