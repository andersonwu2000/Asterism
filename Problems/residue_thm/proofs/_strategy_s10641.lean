import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_param_int_continuous_at_on_closed_ball

namespace Problems.residue_thm

-- Localize to a closed ball: pick r > 0 with ball w₀ r ⊆ U from openness of U,
-- shrink to closedBall w₀ (r/2) ⊆ U, restrict the joint-continuity hF to this
-- compact box, and hand off to the closed-ball-localized continuity sub-goal.
-- Sub-goal: `param_int_continuous_at_on_closed_ball` — the parametric DCT core
-- (joint continuity on a compact closedBall × Icc gives a uniform bound, so
-- intervalIntegral.continuousAt_of_dominated_interval applies at w₀); strictly
-- simpler than the parent because the open-set localization is discharged here.
theorem s10641
    {U : Set ℂ} {a b : ℝ} {F : ℂ → ℝ → ℂ}
    (hU : IsOpen U)
    (hF : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2) (U ×ˢ Set.Icc a b))
    {w₀ : ℂ} (hw₀ : w₀ ∈ U) :
    ContinuousAt (fun w => ∫ t in a..b, F w t) w₀  := by
  obtain ⟨r, hr, hball⟩ := Metric.isOpen_iff.mp hU w₀ hw₀
  have hr2 : (0 : ℝ) < r / 2 := by linarith
  have hsubset : Metric.closedBall w₀ (r/2) ⊆ U :=
    (Metric.closedBall_subset_ball (by linarith)).trans hball
  have hF' : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2)
      (Metric.closedBall w₀ (r/2) ×ˢ Set.Icc a b) :=
    hF.mono (Set.prod_mono hsubset Set.Subset.rfl)
  exact param_int_continuous_at_on_closed_ball w₀ (r/2) hr2 hF'

end Problems.residue_thm
