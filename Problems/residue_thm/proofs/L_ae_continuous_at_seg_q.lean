import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- ae_continuous_at_seg_q: ContinuousAt.comp_of_eq + Filter.Eventually.of_forall; Q∘(z+t·h)
-- is continuous at h=0 for every t since hQ gives ContinuousAt Q z and z+t·0=z.
-- entry_kind: Builder
theorem ae_continuous_at_seg_q
    (Q : ℂ → ℂ) (z : ℂ) (R : ℝ) (hR : 0 < R)
    (hQ : ContinuousOn Q (Metric.closedBall z R)) :
    ∀ᵐ t ∂(MeasureTheory.volume : MeasureTheory.Measure ℝ),
      t ∈ Set.uIoc (0:ℝ) 1 → ContinuousAt (fun h : ℂ => Q (z + (t : ℂ) * h)) 0 := by
  apply Filter.Eventually.of_forall
  intro t _ht
  apply (hQ.continuousAt (Metric.closedBall_mem_nhds z hR)).comp_of_eq (by fun_prop)
  simp

end Problems.residue_thm
