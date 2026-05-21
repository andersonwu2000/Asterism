import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- integrand_joint_continuous_on_ball_icc: joint ContinuousOn of the Cauchy integrand
-- on ball z r ×ˢ Icc 0 1 using ContDiffOn.continuousOn_derivWithin + div nonzero.
theorem integrand_joint_continuous_on_ball_icc
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hr : 0 < r)
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, r < dist (γ t) z) :
    ContinuousOn
      (fun p : ℂ × ℝ => derivWithin γ (Set.Icc 0 1) p.2 / (γ p.2 - p.1))
    (Metric.ball z r ×ˢ Set.Icc 0 1) := by
  apply ContinuousOn.div
  · -- numerator: derivWithin γ (Icc 0 1) p.2 continuous on product
    exact (hγ.continuousOn_derivWithin (uniqueDiffOn_Icc zero_lt_one) le_rfl).comp
      continuous_snd.continuousOn (fun p hp => hp.2)
  · -- denominator: γ p.2 - p.1 continuous on product
    apply ContinuousOn.sub
    · exact hγ.continuousOn.comp continuous_snd.continuousOn (fun p hp => hp.2)
    · exact continuous_fst.continuousOn
  · -- denominator nonzero on domain
    intro ⟨w, t⟩ ⟨hw, ht⟩ heq
    have hdw : dist w z < r := Metric.mem_ball.mp hw
    have hdγ : r < dist (γ t) z := h_avoid t ht
    have hne : γ t ≠ w := by
      intro h
      have heqdist : dist (γ t) z = dist w z := by rw [h]
      linarith [heqdist ▸ hdγ]
    exact hne (sub_eq_zero.mp heq)

end Problems.residue_thm
