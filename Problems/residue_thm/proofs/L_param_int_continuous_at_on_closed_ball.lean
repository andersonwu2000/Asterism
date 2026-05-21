import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem param_int_continuous_at_on_closed_ball
    {a b : ℝ} {F : ℂ → ℝ → ℂ}
    (w₀ : ℂ) (r : ℝ) (hr : 0 < r)
    (hF : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2)
            (Metric.closedBall w₀ r ×ˢ Set.Icc a b)) :
    ContinuousAt (fun w => ∫ t in a..b, F w t) w₀ := by sorry

end Problems.residue_thm
