-- Decompose into:
-- (a) integrand_match_right_half_to_compose: rewrite LHS via h = β'(2·-1) on [1/2,1]
--     (chain rule turns deriv h t into 2 · deriv β' (2t-1) a.e. on the interval),
-- (b) subst_linear_2t_minus_1: pure linear u-substitution u = 2t-1
--     on a C¹ β' over [0,1]; absorbs the factor 2 from the chain rule.
-- Chain via Eq.trans.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10677

namespace Problems.residue_thm

def subst_h_eq_beta_right_half := @Problems.residue_thm.s10677

end Problems.residue_thm
