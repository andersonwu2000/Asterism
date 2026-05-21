-- Apply `intervalIntegral.integral_add_adjacent_intervals` at the midpoint `1/2`.
-- The combinator closes the parent (a = ∫_{[0,1]}, b + c = ∫_{[0,1/2]} + ∫_{[1/2,1]})
-- via `.symm`. Sub-goals: `IntervalIntegrable` for the integrand on each half.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10668

namespace Problems.residue_thm

def flat_ftc_int_additivity_at_half := @Problems.residue_thm.s10668

end Problems.residue_thm
