-- Reduce to abstract quadratic-root construction: setting v(x) = x - f(x),
-- v is continuous (hcont), nowhere zero (hnofp), and satisfies the sphere
-- inner-positivity ⟨x, v(x)⟩ ≥ 0 (hmaps + Cauchy–Schwarz). The substantive
-- sub-goal eliminates f entirely and builds t purely from these abstract
-- conditions on v.
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10820

namespace Problems.Topology.brouwer_fixed_point

def exists_continuous_ray_parameter := @Problems.Topology.brouwer_fixed_point.s10820

end Problems.Topology.brouwer_fixed_point
