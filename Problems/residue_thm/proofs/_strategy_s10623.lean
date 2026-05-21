import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_param_int_continuous_on_open_of_joint

namespace Problems.residue_thm

-- Single abstract bridge sub-goal: replace the specific `Metric.ball z r` by a
-- generic open set `U` and the specific endpoints `0..1` by generic `a..b`, then
-- the parent goal is one immediate application of the bridge at
-- `U := Metric.ball z r`, `a := 0`, `b := 1` using `Metric.isOpen_ball`.
theorem s10623
    {z : ℂ} {r : ℝ} {F : ℂ → ℝ → ℂ}
    (hr : 0 < r)
    (hF : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2)
            (Metric.ball z r ×ˢ Set.Icc 0 1)) :
    ContinuousOn (fun w => ∫ t in (0:ℝ)..1, F w t) (Metric.ball z r)  := by
  exact param_int_continuous_on_open_of_joint Metric.isOpen_ball hF

end Problems.residue_thm
