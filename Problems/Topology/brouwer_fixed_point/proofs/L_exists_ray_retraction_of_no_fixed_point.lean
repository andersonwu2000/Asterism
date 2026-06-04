-- Build the retraction r(x) := x + t(x) • (x - f(x)) by the classic
-- ray-from-f(x)-through-x construction.
-- Sub-goal A produces the scaling parameter t : Dⁿ → ℝ (continuous on Dⁿ,
-- normalising the ray-endpoint to the sphere, vanishing on Sⁿ⁻¹) — the
-- geometric crux (uses hmaps + hnofp).
-- Sub-goal B assembles r from any such t (pure algebra; needs only hcont
-- and continuity of t).
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10818

namespace Problems.Topology.brouwer_fixed_point

def exists_ray_retraction_of_no_fixed_point := @Problems.Topology.brouwer_fixed_point.s10818

end Problems.Topology.brouwer_fixed_point
