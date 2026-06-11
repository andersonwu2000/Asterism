import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs
import Library.Geometry.ManifoldBoundary.BoundaryCoord
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_faceproj_faceembed

namespace Problems.Geometry.stokes_bdry_chart_topo

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

-- Set-extensionality bridge between the `faceProj`-image and `faceEmbed`-preimage
-- descriptions of `chartTarget`. Forward: a witness `w` with `w 0 = 0` round-trips via
-- `faceEmbed_faceProj_of_coord_zero`. Backward: `faceEmbed z` has vanishing zeroth
-- coordinate (`faceEmbed_mem_frontier_range` + `coord_zero_of_frontier_range`) and
-- round-trips via the proved sibling `faceproj_faceembed` (s11673).
theorem s11674 (p : Bdry n M) :
    chartTarget p = faceEmbed ⁻¹' (extChartAt (𝓡∂ (n + 1)) p.val).target  := by
  ext z
  simp only [chartTarget, Set.mem_image, Set.mem_inter_iff, Set.mem_setOf_eq, Set.mem_preimage]
  constructor
  · rintro ⟨w, ⟨hwT, hw0⟩, rfl⟩
    rwa [Library.Geometry.ManifoldBoundary.BoundaryCoord.faceEmbed_faceProj_of_coord_zero w hw0]
  · intro hz
    exact ⟨faceEmbed z, ⟨hz,
      Library.Geometry.ManifoldBoundary.BoundaryCoord.coord_zero_of_frontier_range _
        (faceEmbed_mem_frontier_range z)⟩, faceproj_faceembed z⟩

end Problems.Geometry.stokes_bdry_chart_topo
