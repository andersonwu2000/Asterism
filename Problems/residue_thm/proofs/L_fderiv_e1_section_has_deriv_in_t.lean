-- Schwarz mixed-partial decomposition. Two sub-goals:
-- (A) `fderiv_section_chain_rule_in_t` — chain rule: the t-section of the joint
--     fderivWithin's (1,0)-application has, at t ∈ Ioo, derivative equal to the
--     iterated `fderivWithin (fderivWithin H s) s (τ,t) (0,1) (1,0)`.
-- (B) `schwarz_mixed_partial_bridge` — bridge: that iterated value equals
--     `derivWithin (fun τ' => deriv (H τ') t) (Icc 0 1) τ`, via second-derivative
--     symmetry (`ContDiffWithinAt.isSymmSndFDerivWithinAt`) plus the t-slice
--     chain rule connecting `deriv (H τ') t` to `fderivWithin H s (τ',t) (0,1)`.
-- Combine via `HasDerivAt.congr_deriv hA hB`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10355

namespace Problems.residue_thm

def fderiv_e1_section_has_deriv_in_t := @Problems.residue_thm.s10355

end Problems.residue_thm
