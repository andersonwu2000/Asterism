import Mathlib
import Library.Geometry.Manifold.DiffFormBundle
import Library.Geometry.Manifold.DDZero
import Library.Geometry.ManifoldBdry.PullbackFlatForm

/-!
Setup for the integration-current bridge's d-step (brick ②): d-naturality of the flat
pullback. Brick ① (`Library.Geometry.ManifoldBdry.PullbackFlatForm`) proved that the
pullback of a flat test `k`-form `φ : F → Λᵏ F` along a smooth `e : N → F` is a smooth
bundle section `pullbackFlatFormFun e φ`. Here we package it as a genuine `DiffForm` and
state that the manifold exterior derivative commutes with the pullback.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.ManifoldBdry.PullbackFlatForm
open scoped Manifold Bundle ContDiff

namespace Problems.Geometry.pullback_flat_dnat

variable {n k : ℕ}
  {N : Type*} [TopologicalSpace N]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
  {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]

/-- The flat pullback `e* φ` packaged as a genuine smooth `k`-form on the
manifold-with-boundary `N`: the raw section `pullbackFlatFormFun e φ` (brick ①) together
with its harvested fibrewise smoothness `contMDiff_pullbackFlatFormFun`. -/
noncomputable def pullbackFlatForm (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e) (hφ : ContDiff ℝ ∞ φ) :
    DiffForm (𝓡∂ (n + 1)) N k where
  toFun := pullbackFlatFormFun e φ
  contMDiff_toFun := contMDiff_pullbackFlatFormFun e φ he hφ

end Problems.Geometry.pullback_flat_dnat
