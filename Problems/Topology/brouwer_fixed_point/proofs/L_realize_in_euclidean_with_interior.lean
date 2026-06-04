-- Decompose: realize K in a (Submodule) subspace V of E with nonempty interior in V,
-- then transport that "fat" subset to a Euclidean coordinate space via an isometry
-- supplied by the orthonormal-basis machinery on finite-dim inner product spaces.
-- Sub_1 isolates the affine-span / interior-in-its-own-span argument; sub_2 is a
-- straight transport along a known Mathlib isomorphism, with no convexity-from-span
-- reasoning involved.
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10810

namespace Problems.Topology.brouwer_fixed_point

def realize_in_euclidean_with_interior := @Problems.Topology.brouwer_fixed_point.s10810

end Problems.Topology.brouwer_fixed_point
