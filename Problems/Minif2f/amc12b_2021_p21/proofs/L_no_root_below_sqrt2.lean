-- Decompose no-root on (0, √2) by trichotomy on `y` vs 1:
--   (a) y ∈ (0, 1): LHS = y^(2^√2) < 1 and RHS = √2^(2^y) > 1, hence ≠.
--   (b) y ∈ [1, √2): the narrower analytic case (function-comparison /
--       monotonicity of log y / 2^y) on a strictly smaller interval.
-- Each sub-goal keeps the parent's binders + adds one bound on y, so both
-- are strictly simpler than the parent.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9745

namespace Problems.Minif2f.amc12b_2021_p21

def no_root_below_sqrt2 := @Problems.Minif2f.amc12b_2021_p21.s9745

end Problems.Minif2f.amc12b_2021_p21
