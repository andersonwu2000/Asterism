import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- circle_integrable_const_mul_inv: ContinuousOn.circleIntegrable via inv₀; z off sphere ⟹ w-z≠0
-- The constant f z factor is harmless; (w-z)⁻¹ is continuous on the sphere since z ∉ sphere z₀ ρ.
set_option linter.unusedVariables false in
-- entry_kind: Builder
theorem circle_integrable_const_mul_inv
    {f : ℂ → ℂ} {z₀ z : ℂ} {ρ : ℝ}
    (hρ : 0 < ρ)
    (hfcont : ContinuousOn f (Metric.sphere z₀ ρ))
    (hz : z ∉ Metric.sphere z₀ ρ) :
    CircleIntegrable (fun w => f z * (w - z)⁻¹) z₀ ρ := by
  apply ContinuousOn.circleIntegrable hρ.le
  apply ContinuousOn.mul continuousOn_const
  apply (continuousOn_id.sub continuousOn_const).inv₀
  intro w hw h
  exact hz (sub_eq_zero.mp h ▸ hw)

end Problems.residue_thm
