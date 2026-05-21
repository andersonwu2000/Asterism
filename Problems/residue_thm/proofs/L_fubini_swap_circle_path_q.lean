-- Fubini swap on Q-kernel: reduce circle integral to interval over [0, 2π], commute
-- with path integral over [0, 1] via joint integrability of the rational integrand,
-- then refold the circle integral on the other side.
--   (1) `q_kernel_lhs_to_double` — unfold ∮ on the LHS and pull `deriv γ t` inside.
--   (2) `q_kernel_double_fubini_swap` — swap order of integration on the double
--       interval integral (joint integrability of the rational integrand).
--   (3) `q_kernel_double_to_rhs` — pull `deriv (circleMap a ε) θ` inside, refold ∮.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10556

namespace Problems.residue_thm

def fubini_swap_circle_path_q := @Problems.residue_thm.s10556

end Problems.residue_thm
