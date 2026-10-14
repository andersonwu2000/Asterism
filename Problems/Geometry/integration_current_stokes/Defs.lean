import Mathlib
import Problems.Geometry.pullback_flat_dnat.Defs
import Problems.Geometry.pullback_flat_dnat.Root
import Problems.Geometry.stokes_bdry_compact.Defs
import Problems.Geometry.stokes_bdry_manifold.Defs
import Problems.Geometry.stokes_bdry_manifold.Root
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_integral.Defs
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_theorem.Defs
import Problems.Geometry.stokes_theorem.Root

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
open Problems.Geometry.stokes_form_bundle (DiffForm)
open Problems.Geometry.stokes_integral (DiffForm.integral OrientedManifold)
open Problems.Geometry.stokes_bdry_compact (Bdry)
open Problems.Geometry.pullback_flat_dnat (pullbackFlatForm)
open Problems.Geometry.stokes_theorem (pullbackBdry)

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
