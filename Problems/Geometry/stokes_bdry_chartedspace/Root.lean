-- PARKED. mem_chart_source for the boundary ChartedSpace: every boundary point lies
-- in the source of its own chart. `(bdryChart p).source = chartSource p =
-- Subtype.val ⁻¹' (extChartAt p.val).source`, and `p.val ∈ (extChartAt p.val).source`
-- (`mem_extChartAt_source` / `mem_chart_source`). This is the `mem_chart_source`
-- field P9's ChartedSpace instance consumes.
import Mathlib
import Problems.Geometry.stokes_bdry_chartedspace.Defs

open Library.Geometry.ManifoldBoundary.BoundaryChart
open Library.Geometry.ManifoldBdry.BdryChart

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs

namespace Problems.Geometry.stokes_bdry_chartedspace

-- main: mem_extChartAt_source closes the membership after unfolding bdryChart/chartSource
-- `(bdryChart p).source` reduces definitionally to `Subtype.val ⁻¹' (extChartAt ... p.val).source`
-- so `simp only [bdryChart, chartSource, Set.mem_preimage]` exposes the goal as Mathlib's axiom.
theorem main : ∀ {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M),
    p ∈ (bdryChart p).source := by
  intro n M _ _ _ p
  simp only [bdryChart, chartSource, Set.mem_preimage]
  exact mem_extChartAt_source p.val

end Problems.Geometry.stokes_bdry_chartedspace
