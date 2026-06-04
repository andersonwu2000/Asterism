-- Restrict f to a subtype self-map of S, then transfer the Brouwer-on-T
-- fixed-point fact across `φ : S ≃ₜ T` by conjugation.
-- Sub-goal `restricted_self_map_continuous` packages continuity of the
-- subtype restriction of `f`; sub-goal `fixed_point_subtype_via_homeo`
-- is the abstract conjugation-by-homeomorphism transfer.
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10829

namespace Problems.Topology.brouwer_fixed_point

def fixed_point_transfer_via_homeo := @Problems.Topology.brouwer_fixed_point.s10829

end Problems.Topology.brouwer_fixed_point
