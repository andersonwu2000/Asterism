/-
  Defs.lean — no new vocabulary; cites the boundary chart data from
  `Problems.Geometry.stokes_bdry_chart` (`Defs` for the chart maps), `stokes_bdry_compact`
  for `Bdry`, `stokes_bdry_invfun_mem` for `faceEmbed`. The topological laws of the
  chart (open source/target, continuity both ways) are the Root.
-/
import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs
import Problems.Geometry.stokes_bdry_compact.Defs
import Problems.Geometry.stokes_bdry_invfun_mem.Defs
import Problems.Geometry.stokes_bdry_invfun_mem.proofs.L_faceembed_mem_frontier_range

open scoped Manifold Bundle ContDiff
open Bundle

namespace Problems.Geometry.stokes_bdry_chart_topo

end Problems.Geometry.stokes_bdry_chart_topo
