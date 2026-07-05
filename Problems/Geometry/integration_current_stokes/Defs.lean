import Mathlib
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry
import Library.Geometry.ManifoldBdry.PullbackFlatDNat         -- pullbackFlatForm, mextDeriv_pullbackFlatForm (brick ②)
import Library.Geometry.Manifold.PerBumpStokes                -- pullbackBdry, integral_mextDeriv_eq_integral_pullbackBdry (Stokes)

/-!
Capstone of the de Rham integration-current bridge: classical Stokes on `N` expressed as
the currents boundary identity `∂[[e]] = [[∂e]]`, at the level of the integration
*functionals*. The integration current `[[e]]` of a smooth `e : N → F` pairs a flat test
form `ψ` with `∫_N e* ψ`; its boundary `∂[[e]]` (`ψ ↦ [[e]](dψ)`) equals `[[∂e]]`.

Defined here as plain `ℝ`-valued evaluations. Upgrading `ψ ↦ [[e]](ψ)` to a *continuous*
functional on the LF test-form space — a genuine `Current` — is a separate analytic brick
(a sup-norm bound on `DiffForm.integral`), deferred.
-/

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBdry.PullbackFlatDNat
open Library.Geometry.Manifold.PerBumpStokes

namespace Problems.Geometry.integration_current_stokes

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

end Problems.Geometry.integration_current_stokes
