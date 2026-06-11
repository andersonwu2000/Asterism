-- Set-extensionality bridge between the `faceProj`-image and `faceEmbed`-preimage
-- descriptions of `chartTarget`. Forward: a witness `w` with `w 0 = 0` round-trips via
-- `faceEmbed_faceProj_of_coord_zero`. Backward: `faceEmbed z` has vanishing zeroth
-- coordinate (`faceEmbed_mem_frontier_range` + `coord_zero_of_frontier_range`) and
-- round-trips via the proved sibling `faceproj_faceembed` (s11673).
import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs
import Problems.Geometry.stokes_bdry_chart_topo.proofs._strategy_s11674

namespace Problems.Geometry.stokes_bdry_chart_topo

def chart_target_eq_face_embed_preimage := @Problems.Geometry.stokes_bdry_chart_topo.s11674

end Problems.Geometry.stokes_bdry_chart_topo
