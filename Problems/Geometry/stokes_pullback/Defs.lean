/-
  Defs.lean — owns `faceEmbedL` (the differential `dι` of the boundary inclusion, in
  coordinates: the linear face embedding) and `pullbackBdryFun` (the raw section of
  `∂M`'s form bundle giving `ι* φ`). Cites P4 (`DiffForm`/`formBundleCore`/instances),
  P5 (`formInCoord` + smooth-bundle instance), `Bdry` (CompactBdry), and `∂M`'s
  manifold structure (BdryIsManifold: `instBdryChartedSpace`, `isManifold_bdry`).
  The Root proves `pullbackBdryFun` is a `C^∞` section (so `ι*` is a genuine form).
-/
import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs
import Problems.Geometry.stokes_bdry_chart.proofs.L_boundary_ext_chart_at_coord_zero
import Problems.Geometry.stokes_bdry_chart.proofs.L_face_embed_face_proj_of_coord_zero
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_inv_fun_val_eq_symm_face_embed
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_target_eq_face_embed_preimage
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_target_is_open
import Problems.Geometry.stokes_bdry_compact.Defs
import Problems.Geometry.stokes_bdry_invfun_mem.Defs
import Problems.Geometry.stokes_bdry_invfun_mem.proofs.L_faceembed_mem_frontier_range
import Problems.Geometry.stokes_bdry_manifold.Defs
import Problems.Geometry.stokes_bdry_manifold.Root
import Problems.Geometry.stokes_bdry_manifold.proofs.L_smooth_face_embed
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_form_coord_comp.Defs
import Problems.Geometry.stokes_form_coord_self.Root
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_eq_coord_change
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_smooth

open scoped Manifold Bundle ContDiff
open Bundle
open Problems.Geometry.stokes_form_bundle (DiffForm formBundleCore)
open Problems.Geometry.stokes_mextderiv (formInCoord)
open Problems.Geometry.stokes_bdry_compact (Bdry)

namespace Problems.Geometry.stokes_pullback

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

-- `∂M`'s `IsManifold` is a global `@[instance]` (P9 `isManifold_bdry`), so
-- `formBundleCore (𝓘…) (Bdry n M)` synthesizes it directly — no local register needed.

/-- `dι` of the boundary inclusion in coordinates: the linear face embedding
    `EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin (n+1))` (coords `1..n`). Since
    `ι` becomes `faceEmbed` (linear) in the charts, `dι` is this constant CLM. -/
noncomputable def faceEmbedL :
    EuclideanSpace ℝ (Fin n) →L[ℝ] EuclideanSpace ℝ (Fin (n + 1)) :=
  ∑ i : Fin n, (EuclideanSpace.proj i).smulRight (EuclideanSpace.basisFun (Fin (n + 1)) ℝ i.succ)

/-- Raw section of `∂M`'s form bundle for `ι* φ` at `p`: precompose `φ`'s coordinate
    rep at `p.val` by `faceEmbedL` (= `dι`), transport into the `∂M` fibre. -/
noncomputable def pullbackBdryFun (φ : DiffForm (𝓡∂ (n + 1)) M n) (p : Bdry n M) :
    (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p :=
  Trivialization.symmL ℝ
    (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p) p
    (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
      (formInCoord (𝓡∂ (n + 1)) φ p.val (extChartAt (𝓡∂ (n + 1)) p.val p.val)))

end Problems.Geometry.stokes_pullback
