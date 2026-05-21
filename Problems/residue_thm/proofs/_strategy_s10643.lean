import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_continuous_at_segment_integral_of_continuous_on_closed_ball
import Problems.residue_thm.proofs.L_integral_segment_zero

namespace Problems.residue_thm

-- Split tendsto-to-Q(z) into (value at h=0) + (ContinuousAt at 0):
-- (1) `integral_segment_zero` — Builder: at h=0 the integrand collapses
--     (t·0=0, z+0=z) so ∫₀¹ Q z dt = Q z by `intervalIntegral.integral_const`.
-- (2) `continuousAt_segment_integral_of_continuous_on_closed_ball` — Backward:
--     the parametric integral is continuous at h=0. With Q ContinuousOn a closed
--     ball around z, for ‖h‖ ≤ R the segment t↦z+t·h stays in the ball, giving
--     AEStronglyMeasurable + bound for DCT (`continuousAt_of_dominated_interval`,
--     lesson 30 pattern).
-- Combinator: ContinuousAt unfolds to Tendsto to value-at-0; rewrite via (1).
theorem s10643
    (Q : ℂ → ℂ) (z : ℂ) (R : ℝ) (hR : 0 < R)
    (hQ : ContinuousOn Q (Metric.closedBall z R)) :
    Filter.Tendsto (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h))
      (nhds 0) (nhds (Q z))  := by
  have h_val := integral_segment_zero Q z
  have h_cont := continuous_at_segment_integral_of_continuous_on_closed_ball Q z R hR hQ
  rw [← h_val]
  exact h_cont

end Problems.residue_thm
