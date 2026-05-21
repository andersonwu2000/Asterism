import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem kernel_split_pointwise
    {f : ℂ → ℂ} {z₀ z : ℂ} {ρ : ℝ}
    (hρ : 0 < ρ)
    (hfcont : ContinuousOn f (Metric.sphere z₀ ρ))
    (hz : z ∉ Metric.sphere z₀ ρ) :
    ∀ w ∈ Metric.sphere z₀ ρ,
      f w / (w - z) = f z * (w - z)⁻¹ + (f w - f z) / (w - z) := by grind

end Problems.residue_thm
