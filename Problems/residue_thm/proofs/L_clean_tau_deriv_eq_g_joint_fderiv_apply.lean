-- Bridge the LHS to a cleaned variant whose τ'-integrand is `f (H τ' t) * fderivWithin H_joint
-- (Icc×Icc) (τ', t) (0, 1)` via a t-direction "section derivWithin = fderiv-apply" identity
-- (h_bridge), then close the τ-derivWithin via a section-chain-rule on the cleaned C¹ function
-- (h_clean). The combinator is `derivWithin_congr` (EqOn on Icc 0 1 of the τ' integrand).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10359

namespace Problems.residue_thm

def clean_tau_deriv_eq_g_joint_fderiv_apply := @Problems.residue_thm.s10359

end Problems.residue_thm
