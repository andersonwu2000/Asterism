import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s173_sub_1
import Problems.cantor_xi_measure.proofs.L_s173_sub_2
import Problems.cantor_xi_measure.proofs.L_s173_sub_3

namespace Problems.cantor_xi_measure

theorem s173 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    (∀ n : ℕ, MeasureTheory.volume (cantorSet ξ) ≤ ENNReal.ofReal ((1 - ξ) ^ n)) →
    MeasureTheory.volume (cantorSet ξ) = 0  := by
  intro ξ hξ₁ hξ₂ h
  have h1 : ENNReal.ofReal (1 - ξ) < 1 := s173_sub_1 ξ hξ₁ hξ₂
  have h2 : Filter.Tendsto (fun n : ℕ => ENNReal.ofReal ((1 - ξ) ^ n)) Filter.atTop (nhds 0) :=
    s173_sub_2 ξ hξ₁ hξ₂ h1
  exact s173_sub_3 ξ hξ₁ hξ₂ h h2

end Problems.cantor_xi_measure
