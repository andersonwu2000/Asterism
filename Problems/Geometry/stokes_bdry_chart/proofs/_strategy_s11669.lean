import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs
import Problems.Geometry.stokes_bdry_chart.proofs.L_boundary_mem_frontier_target
import Problems.Geometry.stokes_bdry_chart.proofs.L_coord_zero_of_frontier_range
import Problems.Geometry.stokes_bdry_chart.proofs.L_frontier_range_of_frontier_target

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier

namespace Problems.Geometry.stokes_bdry_chart

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

-- Three-brick chain: q boundary ⇒ chart image in frontier of chart target ⇒ in frontier of
-- model range ⇒ zeroth coordinate vanishes.
-- boundary_mem_frontier_target is chart-independence of the boundary
-- (isBoundaryPoint_iff_of_mem_atlas at chartAt p.val, whose source contains q.val);
-- frontier_range_of_frontier_target is the converse of Library's
-- frontier_target_of_frontier_range (same frontier_inter_open_inter skeleton, read backwards);
-- coord_zero_of_frontier_range is frontier_range_modelWithCornersEuclideanHalfSpace.
theorem s11669 (p q : Bdry n M)
    (hq : q.val ∈ (extChartAt (𝓡∂ (n + 1)) p.val).source) :
    extChartAt (𝓡∂ (n + 1)) p.val q.val 0 = 0  := by
  have hmem : extChartAt (𝓡∂ (n + 1)) p.val q.val ∈
      (extChartAt (𝓡∂ (n + 1)) p.val).target :=
    (extChartAt (𝓡∂ (n + 1)) p.val).map_source hq
  have hft : extChartAt (𝓡∂ (n + 1)) p.val q.val ∈
      frontier (extChartAt (𝓡∂ (n + 1)) p.val).target :=
    boundary_mem_frontier_target p.val q.val hq q.2
  have hfr : extChartAt (𝓡∂ (n + 1)) p.val q.val ∈
      frontier (Set.range (𝓡∂ (n + 1))) :=
    frontier_range_of_frontier_target p.val _ hmem hft
  exact coord_zero_of_frontier_range _ hfr

end Problems.Geometry.stokes_bdry_chart
