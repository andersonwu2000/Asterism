-- Direct differentiation: HasDerivAt of 2^s via `(hasDerivAt_const).rpow (hasDerivAt_id) h_pos`
-- (lessons #5), HasDerivAt of log s via `Real.hasDerivAt_log` (requires t ≠ 0, supplied from
-- 1 < t via `Set.Ioo` membership). Combine with `.mul_const`, `.const_mul`, then `.sub`.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9830

namespace Problems.Minif2f.amc12b_2021_p21

def has_deriv_g_one_sqrt2 := @Problems.Minif2f.amc12b_2021_p21.s9830

end Problems.Minif2f.amc12b_2021_p21
