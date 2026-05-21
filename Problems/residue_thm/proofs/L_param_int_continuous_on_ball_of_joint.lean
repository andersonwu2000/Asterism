-- Reduce to a generic bridge: joint-continuous F on (open U) ×ˢ Icc a b with a ≤ b
-- yields ContinuousOn of the parametric interval-integral on U. The earlier
-- attempt (s10623) lacked `a ≤ b` — without it the bridge is false (Icc a b = ∅
-- when a > b makes the joint-continuity hypothesis vacuous, but the integral
-- becomes -∫ t in b..a, F w t which can be nonzero / discontinuous). Apply at
-- U := Metric.ball z r, a := 0, b := 1 using `Metric.isOpen_ball` and `zero_le_one`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10654

namespace Problems.residue_thm

def param_int_continuous_on_ball_of_joint := @Problems.residue_thm.s10654

end Problems.residue_thm
