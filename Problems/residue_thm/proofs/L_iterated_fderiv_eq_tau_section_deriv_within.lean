-- Schwarz-bridge step (B): (1,0)-direction iterated fderivWithin at (τ,t),
-- evaluated as a CLM at (0,1), equals the τ-section derivWithin of
-- `τ' ↦ (fderivWithin H (Icc×Icc) (τ', t)) (0, 1)` (lesson-34 pattern on τ-side).
-- The single sub-goal provides the `HasDerivWithinAt` for the CLM-applied section;
-- close via `HasDerivWithinAt.derivWithin` with `uniqueDiffOn_Icc_zero_one`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10394

namespace Problems.residue_thm

def iterated_fderiv_eq_tau_section_deriv_within := @Problems.residue_thm.s10394

end Problems.residue_thm
