-- Apply parametric-DCT (`intervalIntegral.continuousAt_of_dominated_interval`).
-- Three Builder sub-goals supply the DCT premises: eventually-AE-measurability
-- of the integrand, eventually-bounded by a constant M, and pointwise continuity
-- at h=0 (since z+t·0=z and Q is continuous at z via hQ + 0 < R).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10649

namespace Problems.residue_thm

def continuous_at_segment_integral_of_continuous_on_closed_ball := @Problems.residue_thm.s10649

end Problems.residue_thm
