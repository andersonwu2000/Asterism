import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_q_continuous_on_closed_ball_of_punctured
import Problems.residue_thm.proofs.L_segment_avg_tendsto_of_continuous_on_closed_ball

namespace Problems.residue_thm

-- Reduce the punctured-continuity hypothesis to closed-ball continuity at z
-- (since z ≠ a forces dist z a > 0, the closed ball of radius dist z a / 2 lies
-- inside the punctured set), then dispatch to the abstract closed-ball DCT step.
-- (1) `q_continuous_on_closed_ball_of_punctured` — Builder: closedBall z (dist z a / 2)
--     ⊆ Set.univ \ {a}, so `h_cont_on.mono` delivers ContinuousOn Q on the closed ball.
-- (2) `segment_avg_tendsto_of_continuous_on_closed_ball` — abstract DCT core:
--     given ContinuousOn Q on a closed ball around z, the segment-average integral
--     tends to Q z. Independent of the puncture point a.
theorem s10640
    {Q : ℂ → ℂ} {a : ℂ}
    (z : ℂ) (hz : z ∈ Set.univ \ ({a} : Set ℂ))
    (h_cont_on : ContinuousOn Q (Set.univ \ ({a} : Set ℂ))) :
    Filter.Tendsto (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h))
      (nhds 0) (nhds (Q z))  := by
  have hzne : z ≠ a := fun h => hz.2 (Set.mem_singleton_iff.mpr h)
  have h_dist_pos : 0 < dist z a := dist_pos.mpr hzne
  have hR : (0 : ℝ) < dist z a / 2 := by linarith
  have h_ball_cont := q_continuous_on_closed_ball_of_punctured z hz h_cont_on
  exact segment_avg_tendsto_of_continuous_on_closed_ball Q z (dist z a / 2) hR h_ball_cont
end Problems.residue_thm
