-- Decompose `ContDiffOn ℝ 1` of the integral primitive into:
-- (1) continuity of the piecewise velocity on `Icc 0 1` (flat-endpoint joins at 1/2),
-- (2) the generic FTC fact that a constant plus the indefinite integral of a continuous
--     function on `Icc 0 1` is `ContDiffOn ℝ 1` on `Icc 0 1`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10665

namespace Problems.residue_thm

def flat_concat_ftc_smooth := @Problems.residue_thm.s10665

end Problems.residue_thm
