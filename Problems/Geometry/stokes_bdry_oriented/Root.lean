-- POU-glue decomposition of the nonvanishing of the induced boundary orientation form.
-- (1) `chartfun_anchor_ne_zero`: the anchored candidate `inducedOrientChartFun p p ≠ 0`
--     (chart-read of `refForm`, nonzero by `OrientedManifold.refForm_ne`, transported by
--     invertible maps). (2) `pou_ne_zero_mem_chart_source`: a nonzero POU weight at `p`
--     puts `p` in the chart-at-`q` source (subordination via `choose_spec`).
-- (3) `chartfun_pos_ray`: on that common chart source the `q`-candidate is a *positive*
--     multiple of the anchored one (positive normal derivative of the boundary transition).
-- (4) `pou_glue_ne_zero`: a finsum of nonneg-weighted positive multiples of a nonzero
--     anchor, with weights summing to 1, is nonzero. `inducedOrient p = inducedOrientFun p`
--     holds definitionally (`DiffForm` coercion), so (4) closes the goal.
import Mathlib
import Problems.Geometry.stokes_bdry_oriented.Defs
import Problems.Geometry.stokes_bdry_oriented.proofs._strategy_s11716

namespace Problems.Geometry.stokes_bdry_oriented

def main := @Problems.Geometry.stokes_bdry_oriented.s11716

end Problems.Geometry.stokes_bdry_oriented
