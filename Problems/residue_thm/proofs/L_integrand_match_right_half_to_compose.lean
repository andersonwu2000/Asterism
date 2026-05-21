-- Reduce integral equality on [1/2,1] to pointwise a.e. equality on Ioo (1/2) 1.
-- Sub-goal `h_deriv_eq_two_beta_deriv_interior` supplies the chain-rule equation
-- `deriv h t = 2 * deriv β' (2*t - 1)` on the open interior; combined with the
-- parent hypothesis `hh_right` for the Q-factor, this closes the integrand
-- equation a.e. on Ioc (1/2) 1 (since Ioo and Ioc differ by {1}, a measure-zero set).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10684

namespace Problems.residue_thm

def integrand_match_right_half_to_compose := @Problems.residue_thm.s10684

end Problems.residue_thm
