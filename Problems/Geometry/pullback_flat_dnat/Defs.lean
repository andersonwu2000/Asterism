import Mathlib
import Problems.Geometry.pullback_flat_form.Defs
import Problems.Geometry.pullback_flat_form.Root
import Problems.Geometry.pullback_flat_form.proofs.L_pullback_flat_chart_read_contdiffon
import Problems.Geometry.pullback_flat_form.proofs.L_pullback_flat_triv_read
import Problems.Geometry.stokes_dd_zero.Defs
import Problems.Geometry.stokes_dd_zero.proofs.L_form_in_coord_mext_deriv_eq
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_mextderiv.Defs

/-!
Setup for the integration-current bridge's d-step (brick ②): d-naturality of the flat
pullback. Brick ① (`Problems.Geometry.pullback_flat_form`) proved that the
pullback of a flat test `k`-form `φ : F → Λᵏ F` along a smooth `e : N → F` is a smooth
bundle section `pullbackFlatFormFun e φ`. Here we package it as a genuine `DiffForm` and
state that the manifold exterior derivative commutes with the pullback.
-/

open Bundle
open Problems.Geometry.stokes_form_bundle (DiffForm)
open Problems.Geometry.pullback_flat_form (pullbackFlatFormFun)
open scoped Manifold Bundle ContDiff

namespace Problems.Geometry.pullback_flat_dnat

variable {n k : ℕ}
  {N : Type*} [TopologicalSpace N]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
  {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]

/-- The flat pullback `e* φ` packaged as a genuine smooth `k`-form on the
manifold-with-boundary `N`: the raw section `pullbackFlatFormFun e φ` (brick ①) together
with its harvested fibrewise smoothness `Problems.Geometry.pullback_flat_form.main`. -/
noncomputable def pullbackFlatForm (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hφ : ContDiff ℝ ∞ φ) :
    DiffForm (𝓡∂ (n + 1)) N k where
  toFun := pullbackFlatFormFun e φ
  contMDiff_toFun := Problems.Geometry.pullback_flat_form.main e φ he hφ

end Problems.Geometry.pullback_flat_dnat
