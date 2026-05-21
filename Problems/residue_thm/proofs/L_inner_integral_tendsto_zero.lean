-- Strip the outer `-((2πi)⁻¹ * ·)` wrapper: it's `Tendsto.const_mul` then `.neg`,
-- so the asymptotic core is just the circle integral going to 0 at cocompact.
-- Sub-goal carries all parent hypotheses and isolates the analytic content.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10419

namespace Problems.residue_thm

def inner_integral_tendsto_zero := @Problems.residue_thm.s10419

end Problems.residue_thm
