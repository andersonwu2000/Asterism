import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_param_int_cont_at_closed_ball_le

namespace Problems.residue_thm

-- Localize the open-set continuity goal to pointwise ContinuousAt at every
-- `w₀ ∈ U`, then shrink to a closed ball `closedBall w₀ (r/2) ⊆ U` (compact)
-- and hand off to the closed-ball DCT core. The single sub-goal
-- `param_int_cont_at_closed_ball_le` carries `a ≤ b`, so the parametric DCT
-- (`continuousAt_of_dominated_interval` with a constant bound from compactness)
-- applies cleanly — this is what was missing in the earlier `_of_joint`
-- (no `a ≤ b`) chain that died at the closed-ball leaf.
theorem s10656
    {U : Set ℂ} {a b : ℝ} {F : ℂ → ℝ → ℂ}
    (hU : IsOpen U) (hab : a ≤ b)
    (hF : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2) (U ×ˢ Set.Icc a b)) :
    ContinuousOn (fun w => ∫ t in a..b, F w t) U  := by
  intro w₀ hw₀
  obtain ⟨r, hr, hball⟩ := Metric.isOpen_iff.mp hU w₀ hw₀
  have hr2 : (0 : ℝ) < r / 2 := by linarith
  have hsubset : Metric.closedBall w₀ (r/2) ⊆ U :=
    (Metric.closedBall_subset_ball (by linarith)).trans hball
  have hF' : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2)
      (Metric.closedBall w₀ (r/2) ×ˢ Set.Icc a b) :=
    hF.mono (Set.prod_mono hsubset Set.Subset.rfl)
  have h_at := param_int_cont_at_closed_ball_le hr2 hab hF'
  exact h_at.continuousWithinAt

end Problems.residue_thm
