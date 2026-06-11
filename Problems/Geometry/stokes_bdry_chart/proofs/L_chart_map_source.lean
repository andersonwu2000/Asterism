import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs
import Problems.Geometry.stokes_bdry_chart.proofs._strategy_s11669

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier

namespace Problems.Geometry.stokes_bdry_chart

-- chart_map_source: chartToFun maps chartSource into chartTarget via map_source +
-- boundary_ext_chart_at_coord_zero (s11669) to place the image in the face slice.
theorem chart_map_source : ∀ {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M), ∀ q ∈ chartSource p, chartToFun p q ∈ chartTarget p := by
  intro n M _ _ _ p q hq
  simp only [chartSource, Set.mem_preimage] at hq
  simp only [chartToFun, chartTarget]
  apply Set.mem_image_of_mem
  constructor
  · exact (extChartAt (𝓡∂ (n + 1)) p.val).map_source hq
  · exact s11669 p q hq

end Problems.Geometry.stokes_bdry_chart

