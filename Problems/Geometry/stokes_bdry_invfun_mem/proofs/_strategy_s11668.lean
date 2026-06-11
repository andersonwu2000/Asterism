import Mathlib
import Problems.Geometry.stokes_bdry_invfun_mem.Defs
import Problems.Geometry.stokes_bdry_invfun_mem.proofs.L_boundary_of_mem_frontier_target
import Problems.Geometry.stokes_bdry_invfun_mem.proofs.L_frontier_target_of_frontier_range

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry

namespace Problems.Geometry.stokes_bdry_invfun_mem

open scoped Manifold ContDiff

-- Decomposition: (A) frontier_target_of_frontier_range — pure topology in the model space:
-- an on-target point of `frontier (range 𝓡∂(n+1))` lies in `frontier (extChartAt _ x).target`
-- (via `extChartAt_target` + `frontier_inter_open_inter`); (B) boundary_of_mem_frontier_target —
-- chart transfer: `isBoundaryPoint_iff_of_mem_atlas` at `e := chartAt _ x` with
-- `PartialEquiv.map_target` / `right_inv` rewrites `e.extend I (symm y)` back to `y`.
-- Combinator: B applied to A's output.
theorem s11668 {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (x : M) (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hy : y ∈ (extChartAt (𝓡∂ (n + 1)) x).target)
    (hfr : y ∈ frontier (Set.range (𝓡∂ (n + 1)))) :
    (extChartAt (𝓡∂ (n + 1)) x).symm y ∈ (𝓡∂ (n + 1)).boundary M  := by
  have h_frontier_target : y ∈ frontier (extChartAt (𝓡∂ (n + 1)) x).target :=
    frontier_target_of_frontier_range x y hy hfr
  exact boundary_of_mem_frontier_target x y hy h_frontier_target

end Problems.Geometry.stokes_bdry_invfun_mem
