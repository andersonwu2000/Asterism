import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- circle_integrable_diff_div: ContinuousOn.circleIntegrable via div continuity + w-z≠0 on sphere
-- entry_kind: Builder
theorem circle_integrable_diff_div
    {f : ℂ → ℂ} {z₀ z : ℂ} {ρ : ℝ}
    (hρ : 0 < ρ)
    (hfcont : ContinuousOn f (Metric.sphere z₀ ρ))
    (hz : z ∉ Metric.sphere z₀ ρ) :
    CircleIntegrable (fun w => (f w - f z) / (w - z)) z₀ ρ := by
  apply ContinuousOn.circleIntegrable hρ.le
  apply ContinuousOn.div
  · exact hfcont.sub continuousOn_const
  · exact (continuous_id.sub continuous_const).continuousOn
  · intro w hw
    exact sub_ne_zero.mpr (fun heq => hz (heq ▸ hw))

end Problems.residue_thm
