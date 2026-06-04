-- Decompose: pick x₀ ∈ K, translate K so that 0 lies inside, embed into V := span(K - x₀);
-- then interior-in-V follows from the abstract fact that a convex compact set containing 0
-- whose linear span is the ambient finite-dim space has nonempty interior.
-- Sub_1 (translate_into_subspace_at_zero) packages the construction (homeomorphism + spanning).
-- Sub_2 (convex_compact_span_top_has_interior) is a pure abstract dimension/interior fact —
-- independent of K, with no homeomorphism reasoning.
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10814

namespace Problems.Topology.brouwer_fixed_point

def realize_in_subspace_with_interior := @Problems.Topology.brouwer_fixed_point.s10814

end Problems.Topology.brouwer_fixed_point
