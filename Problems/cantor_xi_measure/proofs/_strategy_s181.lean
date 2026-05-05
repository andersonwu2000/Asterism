import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s181_sub_1
import Problems.cantor_xi_measure.proofs.L_s181_sub_2

namespace Problems.cantor_xi_measure

theorem s181 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    (∀ n : ℕ, MeasureTheory.volume (cantorSet ξ) ≤ ENNReal.ofReal ((1 - ξ) ^ n)) →
    Filter.Tendsto (fun n : ℕ => ENNReal.ofReal ((1 - ξ) ^ n)) Filter.atTop (nhds 0) →
    MeasureTheory.volume (cantorSet ξ) = 0  := by
  intro ξ hξ₁ hξ₂ h htend
  have hle : MeasureTheory.volume (cantorSet ξ) ≤ 0 := s181_sub_1 ξ hξ₁ hξ₂ h htend
  exact s181_sub_2 ξ hξ₁ hξ₂ h htend hle

end Problems.cantor_xi_measure
