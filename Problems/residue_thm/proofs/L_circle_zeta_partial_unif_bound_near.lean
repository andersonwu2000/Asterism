-- Bound the squared-kernel sup-norm by extracting a uniform `‖g‖` bound on the
-- compact integration sphere and a reverse-triangle denominator bound on the
-- δ-ball around z; combine via M := r * Mg / δ² using ‖deriv (circleMap c r)‖ = r.
-- Sub-goals: (1) g_bounded_on_sphere — compactness+continuity; (2)
-- circle_dist_lower_bound_near_outside — `δ ≤ ‖w-ζ‖` from `r < dist z c`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10446

namespace Problems.residue_thm

def circle_zeta_partial_unif_bound_near := @Problems.residue_thm.s10446

end Problems.residue_thm
