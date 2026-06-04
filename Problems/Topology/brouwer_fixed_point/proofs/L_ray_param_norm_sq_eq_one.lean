-- Expand ‖x + t • v(x)‖² via inner-product polarisation, then reduce the
-- result in (⟨x, v(x)⟩, ‖v(x)‖², ‖x‖²) to a pure ℝ identity.
-- (1) `ray_param_norm_add_smul_sq_expand`: the vector-space expansion
--     ‖x + s • w‖² = ‖x‖² + 2·s·⟨x,w⟩ + s²·‖w‖² (generic, reusable).
-- (2) `ray_param_norm_sq_alg_identity`: pure ℝ identity verifying that the
--     specific choice s = (√(a² + b(1-c)) - a)/b makes the expansion = 1
--     whenever b > 0 and c ≤ 1.
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10824

namespace Problems.Topology.brouwer_fixed_point

def ray_param_norm_sq_eq_one := @Problems.Topology.brouwer_fixed_point.s10824

end Problems.Topology.brouwer_fixed_point
