-- Direct: closed unit ball in `EuclideanSpace ℝ (Fin n)` is convex and
-- contains `0`, hence star-convex at `0`, hence contractible.
-- Closer is `StarConvex.contractibleSpace` applied to `convex_closedBall`.
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10819

namespace Problems.Topology.brouwer_fixed_point

def closed_ball_contractible_space := @Problems.Topology.brouwer_fixed_point.s10819

end Problems.Topology.brouwer_fixed_point
