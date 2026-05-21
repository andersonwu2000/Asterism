import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- q_continuous_on_closed_ball_of_punctured: ContinuousOn.mono — closed ball of radius
-- dist z a / 2 avoids the puncture point a (since z ≠ a), so it lies inside
-- Set.univ \ {a}; the linarith contradiction uses dist z w = dist z a > 0 vs. hw.
theorem q_continuous_on_closed_ball_of_punctured
    {Q : ℂ → ℂ} {a : ℂ}
    (z : ℂ) (hz : z ∈ Set.univ \ ({a} : Set ℂ))
    (h_cont_on : ContinuousOn Q (Set.univ \ ({a} : Set ℂ))) :
    ContinuousOn Q (Metric.closedBall z (dist z a / 2)) := by
  apply h_cont_on.mono
  intro w hw
  simp only [Metric.mem_closedBall] at hw
  simp only [Set.mem_diff, Set.mem_univ, Set.mem_singleton_iff, true_and]
  intro heq
  subst heq
  simp only [Set.mem_diff, Set.mem_univ, Set.mem_singleton_iff, true_and] at hz
  have hdist : 0 < dist z w := dist_pos.mpr hz
  linarith [dist_comm z w]
end Problems.residue_thm
