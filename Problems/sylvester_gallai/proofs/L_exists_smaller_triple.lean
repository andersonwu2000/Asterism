-- Unpack `Collinear p q s` into the parametric form `s = p + t_s*(q - p)` via
-- `collinear_iff_param`; translate `s ≠ p`, `s ≠ q` into `t_s ≠ 0`, `t_s ≠ 1`.
-- The single sub-goal `kelly_smaller_with_param` then handles Kelly's geometric
-- construction (foot of perpendicular, pigeonhole via `three_reals_same_side`,
-- and ratio comparison via `perp_numerator_sq_param_factor`) in explicit
-- parametric form — strictly simpler than the parent because the third
-- collinear point is now a concrete affine combination of `p` and `q`.
import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs._strategy_s10213

namespace Problems.sylvester_gallai

def exists_smaller_triple := @Problems.sylvester_gallai.s10213

end Problems.sylvester_gallai
