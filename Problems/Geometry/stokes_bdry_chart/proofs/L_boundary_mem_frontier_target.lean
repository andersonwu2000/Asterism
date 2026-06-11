import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs

open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier

open scoped Manifold Bundle ContDiff
open Bundle

namespace Problems.Geometry.stokes_bdry_chart

-- boundary_mem_frontier_target: boundary point maps to frontier of extChartAt target
-- Uses isBoundaryPoint_iff_of_mem_atlas (forward direction) with chart_mem_atlas at x;
-- extChartAt = chartAt.extend (𝓡∂) by rfl transfers the result directly.
theorem boundary_mem_frontier_target {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (x q : M) (hq : q ∈ (extChartAt (𝓡∂ (n + 1)) x).source)
    (hbd : q ∈ (𝓡∂ (n + 1)).boundary M) :
    extChartAt (𝓡∂ (n + 1)) x q ∈ frontier (extChartAt (𝓡∂ (n + 1)) x).target := by
  have hqs : q ∈ (chartAt (EuclideanHalfSpace (n + 1)) x).source := by
    rwa [← extChartAt_source (𝓡∂ (n + 1)) x]
  have hbd' : (𝓡∂ (n + 1)).IsBoundaryPoint q := hbd
  rw [ModelWithCorners.isBoundaryPoint_iff_of_mem_atlas
      (hn := (by exact_mod_cast ENat.top_ne_zero : (∞ : WithTop ℕ∞) ≠ 0))
      (he := chart_mem_atlas _ x)
      (hx := hqs)] at hbd'
  have : (chartAt (EuclideanHalfSpace (n + 1)) x).extend (𝓡∂ (n + 1)) =
      extChartAt (𝓡∂ (n + 1)) x := rfl
  rw [this] at hbd'
  exact hbd'

end Problems.Geometry.stokes_bdry_chart
