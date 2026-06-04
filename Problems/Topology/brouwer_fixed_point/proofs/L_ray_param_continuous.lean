-- Direct continuity proof: ‖v x‖^2 ≠ 0 from hvne lets us apply `ContinuousOn.div`;
-- numerator decomposes via sqrt/sub/add/mul on continuous building blocks (id, hvcont,
-- their inner product, and norm-squared).
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10822

namespace Problems.Topology.brouwer_fixed_point

def ray_param_continuous := @Problems.Topology.brouwer_fixed_point.s10822

end Problems.Topology.brouwer_fixed_point
