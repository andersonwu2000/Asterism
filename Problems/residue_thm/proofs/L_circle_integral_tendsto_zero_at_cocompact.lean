-- Squeeze: the circle integral's norm is eventually bounded by M / (‖z - z₀‖ - R/2)
-- (analytic estimate via uniform bound on f over the sphere; sub-goal 1), and
-- that bound tends to 0 at cocompact ℂ (asymptotic, sub-goal 2).
-- Combine via tendsto_zero_iff_norm_tendsto_zero + squeeze_zero'.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10423

namespace Problems.residue_thm

def circle_integral_tendsto_zero_at_cocompact := @Problems.residue_thm.s10423

end Problems.residue_thm
