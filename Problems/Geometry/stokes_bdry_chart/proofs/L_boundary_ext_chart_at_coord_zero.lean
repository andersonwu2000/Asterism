-- Three-brick chain: q boundary ⇒ chart image in frontier of chart target ⇒ in frontier of
-- model range ⇒ zeroth coordinate vanishes.
-- boundary_mem_frontier_target is chart-independence of the boundary
-- (isBoundaryPoint_iff_of_mem_atlas at chartAt p.val, whose source contains q.val);
-- frontier_range_of_frontier_target is the converse of Library's
-- frontier_target_of_frontier_range (same frontier_inter_open_inter skeleton, read backwards);
-- coord_zero_of_frontier_range is frontier_range_modelWithCornersEuclideanHalfSpace.
import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs
import Problems.Geometry.stokes_bdry_chart.proofs._strategy_s11669

namespace Problems.Geometry.stokes_bdry_chart

def boundary_ext_chart_at_coord_zero := @Problems.Geometry.stokes_bdry_chart.s11669

end Problems.Geometry.stokes_bdry_chart
