import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier

open scoped Manifold

namespace Problems.Geometry.stokes_bdry_chart

-- coord_zero_of_frontier_range: frontier of half-space model range equals {y | y 0 = 0},
-- so membership gives the zeroth-coordinate vanishing directly.
theorem coord_zero_of_frontier_range {n : ℕ} (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hfr : y ∈ frontier (Set.range (𝓡∂ (n + 1)))) :
    y 0 = 0 := by
  haveI : NeZero (n + 1) := ⟨Nat.succ_ne_zero n⟩
  rw [frontier_range_modelWithCornersEuclideanHalfSpace] at hfr
  exact hfr.symm

end Problems.Geometry.stokes_bdry_chart
