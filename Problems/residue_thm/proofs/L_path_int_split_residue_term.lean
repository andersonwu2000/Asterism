-- Pointwise distribute `(P (γ t) - r/(γ t - a)) * γ'(t)` and split the integral by linearity.
-- (a) path_integrand_intvl_integrable: `t ↦ P (γ t) * deriv γ t` is interval-integrable on [0,1].
-- (b) residue_kernel_intvl_integrable: `t ↦ deriv γ t / (γ t - a)` is interval-integrable on [0,1].
-- Combine via `intervalIntegral.integral_congr` (ring identity), then `integral_sub` to peel off
-- the second integrand, then `integral_const_mul` pulls the residue scalar out.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10484

namespace Problems.residue_thm

def path_int_split_residue_term := @Problems.residue_thm.s10484

end Problems.residue_thm
