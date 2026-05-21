import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- param_int_cont_at_closed_ball_le: ContinuousAt of parametric interval integral via DCT
-- with constant bound from compactness of closedBall × Icc.
theorem param_int_cont_at_closed_ball_le
    {a b : ℝ} {F : ℂ → ℝ → ℂ} {w₀ : ℂ} {r : ℝ}
    (hr : 0 < r) (hab : a ≤ b)
    (hF : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2)
            (Metric.closedBall w₀ r ×ˢ Set.Icc a b)) :
    ContinuousAt (fun w => ∫ t in a..b, F w t) w₀ := by
  have hcpt : IsCompact (Metric.closedBall w₀ r ×ˢ Set.Icc a b) :=
    (isCompact_closedBall w₀ r).prod isCompact_Icc
  obtain ⟨M, hM⟩ := hcpt.exists_bound_of_continuousOn hF
  have uIoc_sub : Set.uIoc a b ⊆ Set.Icc a b := by
    rw [Set.uIoc_of_le hab]; exact Set.Ioc_subset_Icc_self
  apply intervalIntegral.continuousAt_of_dominated_interval (bound := fun _ => M)
  · filter_upwards [Metric.closedBall_mem_nhds w₀ hr] with w hw
    apply ContinuousOn.aestronglyMeasurable _ measurableSet_uIoc
    exact (hF.comp (continuousOn_const.prodMk continuousOn_id)
        (fun t ht => ⟨hw, ht⟩)).mono uIoc_sub
  · filter_upwards [Metric.closedBall_mem_nhds w₀ hr] with w hw
    filter_upwards using fun t ht => hM ⟨w, t⟩ ⟨hw, uIoc_sub ht⟩
  · exact intervalIntegrable_const
  · filter_upwards using fun t ht => by
      apply ContinuousOn.continuousAt _ (Metric.closedBall_mem_nhds w₀ hr)
      exact hF.comp (continuousOn_id.prodMk continuousOn_const)
        (fun w hw => ⟨hw, uIoc_sub ht⟩)

end Problems.residue_thm
