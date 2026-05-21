-- Decompose into (a) the inner section-derivWithin identity
-- `derivWithin (H τ) (Icc) t = fderivWithin H_joint (Icc×Icc) (τ, t) (0,1)` and
-- (b) the τ-section chain rule for the joint smooth `g` (which gives the τ-derivWithin
-- of `(fun τ' => g(τ', t))` as the (1,0)-fderivWithin of `g` at `(τ, t)`). Combine via
-- `derivWithin_congr` (rewriting the inner derivWithin to fderivWithin pointwise on Icc).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10364

namespace Problems.residue_thm

def tau_dw_eq_fderiv_apply_on_icc_prod := @Problems.residue_thm.s10364

end Problems.residue_thm
