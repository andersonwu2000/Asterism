import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- circle_zeta_partial_aemeas_at_z: AEStronglyMeasurable of the zeta-partial circle integrand
-- Continuity: deriv_circleMap + ContinuousOn.comp_continuous + denominator nonzero outside circle.


theorem circle_zeta_partial_aemeas_at_z
    {g : ℂ → ℂ} {c : ℂ} {r : ℝ} (hr : 0 < r)
    (hg : ContinuousOn g (Metric.sphere c r))
    (z : ℂ) (hz : r < dist z c) :
    MeasureTheory.AEStronglyMeasurable
      (fun θ => deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - z) ^ 2))
      (MeasureTheory.volume.restrict (Set.uIoc (0:ℝ) (2 * Real.pi))) := by
  apply Continuous.aestronglyMeasurable
  simp_rw [deriv_circleMap]
  apply Continuous.smul
  · exact (continuous_circleMap 0 r).mul continuous_const
  · apply Continuous.div
    · exact hg.comp_continuous (continuous_circleMap c r)
          (fun θ => circleMap_mem_sphere c hr.le θ)
    · exact ((continuous_circleMap c r).sub continuous_const).pow 2
    · intro θ
      apply pow_ne_zero
      intro heq
      have hmem := circleMap_mem_sphere c hr.le θ
      rw [Metric.mem_sphere] at hmem
      have hdc : dist z c = r := by
        have hq := sub_eq_zero.mp heq; rw [← hq]; exact hmem
      linarith


end Problems.residue_thm

