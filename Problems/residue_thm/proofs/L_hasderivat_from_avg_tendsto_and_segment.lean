-- Bridge HasDerivAt at z via `hasDerivAt_iff_tendsto_slope_zero`: the slope
-- `t⁻¹ • (F (z + t) - F z)` agrees with the segment-average `∫ Q (z + t' · t)`
-- on a punctured ball (via h_seg, dividing by t), and the average tends to Q z
-- (h_avg); the algebraic-bridge sub-goal packages this congr' + filter restrict.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10550

namespace Problems.residue_thm

def hasderivat_from_avg_tendsto_and_segment := @Problems.residue_thm.s10550

end Problems.residue_thm
