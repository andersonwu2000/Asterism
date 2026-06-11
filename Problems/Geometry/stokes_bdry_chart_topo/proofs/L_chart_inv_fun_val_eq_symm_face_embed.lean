import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_target_eq_face_embed_preimage

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs

namespace Problems.Geometry.stokes_bdry_chart_topo

-- chart_inv_fun_val_eq_symm_face_embed: on chartTarget, chartInvFun p z takes the dite
-- then-branch (faceEmbed z ∈ extChartAt.target via chart_target_eq_face_embed_preimage),
-- so .val = (extChartAt (𝓡∂ (n+1)) p.val).symm (faceEmbed z).
theorem chart_inv_fun_val_eq_symm_face_embed {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M) : ∀ z ∈ chartTarget p,
      (chartInvFun p z).val = (extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z) := by
  intro z hz
  have hmem : faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target := by
    have h := chart_target_eq_face_embed_preimage p
    rw [h] at hz; exact hz
  simp only [chartInvFun, dif_pos hmem]


end Problems.Geometry.stokes_bdry_chart_topo
