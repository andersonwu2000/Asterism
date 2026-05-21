import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10412

namespace Problems.residue_thm

-- inner_principal_part_step_wrapper: delegates to s10412 which proves the same existential
-- statement (inner Cauchy integral construction at isolated singularity z₀, radius R).
theorem inner_principal_part_step_wrapper
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∃ (P : ℂ → ℂ), AnalyticOn ℂ P (Set.univ \ {z₀}) ∧
      Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0) ∧
      ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z)) := by
  exact s10412 hR hf

end Problems.residue_thm
