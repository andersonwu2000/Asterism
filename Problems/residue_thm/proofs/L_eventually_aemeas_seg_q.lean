import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- eventually_aemeas_seg_q: for h near 0, t ↦ Q(z + t·h) is AEStronglyMeasurable on uIoc 0 1
-- For ‖h‖ < R the affine path lands in Metric.closedBall z R (|t| ≤ 1 on uIoc 0 1),
-- so ContinuousOn.comp + ContinuousOn.aestronglyMeasurable close the goal.
theorem eventually_aemeas_seg_q
    (Q : ℂ → ℂ) (z : ℂ) (R : ℝ) (hR : 0 < R)
    (hQ : ContinuousOn Q (Metric.closedBall z R)) :
    ∀ᶠ h in nhds (0:ℂ),
      MeasureTheory.AEStronglyMeasurable (fun t : ℝ => Q (z + (t : ℂ) * h))
        (MeasureTheory.volume.restrict (Set.uIoc (0:ℝ) 1)) := by
  apply Filter.Eventually.mono (Metric.ball_mem_nhds 0 hR)
  intro h hh
  rw [dist_zero_right] at hh
  apply ContinuousOn.aestronglyMeasurable _ measurableSet_uIoc
  apply hQ.comp
    ((continuous_const.add (Complex.continuous_ofReal.mul continuous_const)).continuousOn)
  intro t ht
  simp only [Pi.add_apply, Pi.mul_apply, Metric.mem_closedBall,
             Complex.dist_eq, add_sub_cancel_left]
  rw [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)] at ht
  rw [norm_mul, Complex.norm_real]
  calc |t| * ‖h‖ ≤ 1 * ‖h‖ := by
        apply mul_le_mul_of_nonneg_right _ (norm_nonneg _)
        rw [abs_of_pos ht.1]; exact ht.2
    _ = ‖h‖ := one_mul _
    _ ≤ R := hh.le

end Problems.residue_thm