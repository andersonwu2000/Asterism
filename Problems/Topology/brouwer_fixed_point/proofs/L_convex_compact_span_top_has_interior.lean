-- Decompose: pre-compose the Mathlib equivalence
-- `Convex.interior_nonempty_iff_affineSpan_eq_top` with the bridge from
-- `Submodule.span ℝ T = ⊤` (linear span) + `0 ∈ T` to `affineSpan ℝ T = ⊤`.
-- Sub_1 (affine_span_eq_top_of_zero_mem) is the pure affine-vs-linear-span
-- bridge — no convex / compact / interior content, just affine geometry.
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10816

namespace Problems.Topology.brouwer_fixed_point

def convex_compact_span_top_has_interior := @Problems.Topology.brouwer_fixed_point.s10816

end Problems.Topology.brouwer_fixed_point
