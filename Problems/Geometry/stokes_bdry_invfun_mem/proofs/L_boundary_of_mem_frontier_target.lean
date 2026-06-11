import Mathlib
import Problems.Geometry.stokes_bdry_invfun_mem.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry

namespace Problems.Geometry.stokes_bdry_invfun_mem

open scoped Manifold ContDiff

-- boundary_of_mem_frontier_target: chart transfer via isBoundaryPoint_iff_of_mem_atlas + right_inv
theorem boundary_of_mem_frontier_target {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (x : M) (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hy : y ∈ (extChartAt (𝓡∂ (n + 1)) x).target)
    (hft : y ∈ frontier (extChartAt (𝓡∂ (n + 1)) x).target) :
    (extChartAt (𝓡∂ (n + 1)) x).symm y ∈ (𝓡∂ (n + 1)).boundary M := by
  rw [ModelWithCorners.boundary, Set.mem_setOf_eq]
  have hx_src : (extChartAt (𝓡∂ (n + 1)) x).symm y ∈
      (chartAt (EuclideanHalfSpace (n + 1)) x).source := by
    rw [← extChartAt_source (𝓡∂ (n + 1)) x]
    exact (extChartAt (𝓡∂ (n + 1)) x).map_target hy
  rw [ModelWithCorners.isBoundaryPoint_iff_of_mem_atlas
      (hn := (by exact_mod_cast ENat.top_ne_zero : (∞ : WithTop ℕ∞) ≠ 0))
      (he := chart_mem_atlas _ x)
      (hx := hx_src)]
  have : (chartAt (EuclideanHalfSpace (n + 1)) x).extend (𝓡∂ (n + 1)) =
      extChartAt (𝓡∂ (n + 1)) x := rfl
  rw [this, (extChartAt (𝓡∂ (n + 1)) x).right_inv hy]
  exact hft

end Problems.Geometry.stokes_bdry_invfun_mem
