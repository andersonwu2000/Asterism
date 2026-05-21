import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_param_int_continuous_on_open_of_joint_le

namespace Problems.residue_thm

-- Reduce to a generic bridge: joint-continuous F on (open U) ×ˢ Icc a b with a ≤ b
-- yields ContinuousOn of the parametric interval-integral on U. The earlier
-- attempt (s10623) lacked `a ≤ b` — without it the bridge is false (Icc a b = ∅
-- when a > b makes the joint-continuity hypothesis vacuous, but the integral
-- becomes -∫ t in b..a, F w t which can be nonzero / discontinuous). Apply at
-- U := Metric.ball z r, a := 0, b := 1 using `Metric.isOpen_ball` and `zero_le_one`.
theorem s10654
    {z : ℂ} {r : ℝ} {F : ℂ → ℝ → ℂ}
    (hr : 0 < r)
    (hF : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2)
            (Metric.ball z r ×ˢ Set.Icc 0 1)) :
    ContinuousOn (fun w => ∫ t in (0:ℝ)..1, F w t) (Metric.ball z r)  := by
  exact param_int_continuous_on_open_of_joint_le
    (U := Metric.ball z r) (a := 0) (b := 1) (F := F)
    Metric.isOpen_ball zero_le_one hF

end Problems.residue_thm
