import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- eventually_bounded_seg_q: bound ‖Q(z+t·h)‖ by the max norm of Q on closedBall z R
-- ProperSpace ℂ → closedBall compact; extreme value gives M; h in ball 0 R keeps z+t·h in ball.
theorem eventually_bounded_seg_q
    (Q : ℂ → ℂ) (z : ℂ) (R : ℝ) (hR : 0 < R)
    (hQ : ContinuousOn Q (Metric.closedBall z R)) :
    ∃ M : ℝ, ∀ᶠ h in nhds (0:ℂ),
      ∀ᵐ t ∂(MeasureTheory.volume : MeasureTheory.Measure ℝ),
        t ∈ Set.uIoc (0:ℝ) 1 → ‖Q (z + (t : ℂ) * h)‖ ≤ M := by
  have hcpt : IsCompact (Metric.closedBall z R) := isCompact_closedBall z R
  have hne : (Metric.closedBall z R).Nonempty := Metric.nonempty_closedBall.mpr hR.le
  obtain ⟨w₀, _, hmax⟩ := hcpt.exists_isMaxOn hne hQ.norm
  refine ⟨‖Q w₀‖, ?_⟩
  filter_upwards [Metric.ball_mem_nhds (0 : ℂ) hR] with h hh
  apply MeasureTheory.ae_of_all
  intro t ht
  have htI : (0:ℝ) ≤ t ∧ t ≤ 1 := by
    have h1 := ht
    rw [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)] at h1
    exact ⟨le_of_lt h1.1, h1.2⟩
  have ht1 : ‖(t : ℂ)‖ ≤ 1 := by
    have heq : ‖(t : ℂ)‖ = |t| := RCLike.norm_ofReal t
    rw [heq, abs_of_nonneg htI.1]; exact htI.2
  have hmem : z + (t : ℂ) * h ∈ Metric.closedBall z R := by
    rw [Metric.mem_closedBall]
    calc dist (z + (t : ℂ) * h) z
        = ‖(t : ℂ) * h‖ := by rw [dist_comm]; simp [dist_eq_norm]
      _ ≤ ‖(t : ℂ)‖ * ‖h‖ := norm_mul_le _ _
      _ ≤ 1 * ‖h‖ := by nlinarith [norm_nonneg h, ht1]
      _ = ‖h‖ := one_mul _
      _ ≤ R := by rw [← dist_zero_right]; exact (Metric.mem_ball.mp hh).le
  exact hmax hmem

end Problems.residue_thm
