-- Decompose: (1) translate K by -x₀ to a set K' ⊆ E containing 0 (homeomorphism preserved),
-- (2) embed K' into V := span K' as T ⊆ V satisfying nonempty/compact/convex/0∈T/span T = ⊤
-- and K' ≃ₜ T. Combine via K ≃ₜ K' ≃ₜ T. hns is unused at this level.
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10815

namespace Problems.Topology.brouwer_fixed_point

def translate_into_subspace_at_zero := @Problems.Topology.brouwer_fixed_point.s10815

end Problems.Topology.brouwer_fixed_point
