import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs

namespace Problems.Geometry.stokes_bdry_chart_topo

-- chart_source_is_open: chartSource p is the subtype preimage of an open extChartAt source
theorem chart_source_is_open {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M) : IsOpen (chartSource p) := by
  unfold chartSource
  exact (isOpen_extChartAt_source p.val).preimage continuous_subtype_val

end Problems.Geometry.stokes_bdry_chart_topo
