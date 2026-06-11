import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_target_eq_face_embed_preimage
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_continuous_face_embed

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs

namespace Problems.Geometry.stokes_bdry_chart_topo

-- continuous_on_symm_comp_face_embed: ContinuousOn for extChartAt symm composed with faceEmbed
-- on chartTarget p, using chart_target_eq_face_embed_preimage to get MapsTo then composing
-- continuousOn_extChartAt_symm with continuous_face_embed.continuousOn
theorem continuous_on_symm_comp_face_embed {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M) : ContinuousOn
      (fun z : EuclideanSpace ℝ (Fin n) => (extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z))
      (chartTarget p) := by
  have hmaps : Set.MapsTo faceEmbed (chartTarget p) (extChartAt (𝓡∂ (n + 1)) p.val).target := by
    intro z hz
    rw [chart_target_eq_face_embed_preimage p] at hz
    exact hz
  exact (continuousOn_extChartAt_symm p.val).comp
    continuous_face_embed.continuousOn hmaps

end Problems.Geometry.stokes_bdry_chart_topo

