import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_target_eq_face_embed_preimage
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_continuous_face_embed
import Library.Geometry.ManifoldBoundary.BoundaryCoord

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs

namespace Problems.Geometry.stokes_bdry_chart_topo

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

-- chart_target_is_open: IsOpen (chartTarget p) via the faceEmbed-preimage rewrite and
-- openness of (chartAt _).target pulled back through (𝓡∂ (n+1)).symm ∘ faceEmbed
theorem chart_target_is_open (p : Bdry n M) : IsOpen (chartTarget p) := by
  haveI : NeZero (n + 1) := ⟨Nat.succ_ne_zero n⟩
  rw [chart_target_eq_face_embed_preimage p, extChartAt_target]
  rw [Set.preimage_inter]
  have h_range_univ : faceEmbed ⁻¹' Set.range (𝓡∂ (n + 1)) = Set.univ := by
    ext z
    simp only [Set.mem_preimage, Set.mem_univ, iff_true,
      range_modelWithCornersEuclideanHalfSpace, Set.mem_setOf_eq]
    have := Library.Geometry.ManifoldBoundary.BoundaryCoord.coord_zero_of_frontier_range
      (faceEmbed z) (faceEmbed_mem_frontier_range z)
    linarith
  rw [h_range_univ, Set.inter_univ]
  exact ((chartAt (EuclideanHalfSpace (n + 1)) p.val).open_target.preimage
    (𝓡∂ (n + 1)).continuous_symm).preimage continuous_face_embed

end Problems.Geometry.stokes_bdry_chart_topo
