-- Direct proof: pick distinct a b : A (Nontrivial), then f a = f b by Subsingleton,
-- so applying g and assuming g ∘ f = id forces a = b, contradicting hab.
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10808

namespace Problems.Topology.brouwer_fixed_point

def not_id_factor_through_subsingleton := @Problems.Topology.brouwer_fixed_point.s10808

end Problems.Topology.brouwer_fixed_point
