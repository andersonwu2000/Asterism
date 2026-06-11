-- Decomposition: (A) frontier_target_of_frontier_range — pure topology in the model space:
-- an on-target point of `frontier (range 𝓡∂(n+1))` lies in `frontier (extChartAt _ x).target`
-- (via `extChartAt_target` + `frontier_inter_open_inter`); (B) boundary_of_mem_frontier_target —
-- chart transfer: `isBoundaryPoint_iff_of_mem_atlas` at `e := chartAt _ x` with
-- `PartialEquiv.map_target` / `right_inv` rewrites `e.extend I (symm y)` back to `y`.
-- Combinator: B applied to A's output.
import Mathlib
import Problems.Geometry.stokes_bdry_invfun_mem.Defs
import Problems.Geometry.stokes_bdry_invfun_mem.proofs._strategy_s11668

namespace Problems.Geometry.stokes_bdry_invfun_mem

def symm_mem_boundary_of_frontier := @Problems.Geometry.stokes_bdry_invfun_mem.s11668

end Problems.Geometry.stokes_bdry_invfun_mem
