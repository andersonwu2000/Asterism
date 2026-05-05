import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s180_sub_1
import Problems.cantor_xi_measure.proofs.L_s180_sub_2
import Problems.cantor_xi_measure.proofs.L_s180_sub_3

namespace Problems.cantor_xi_measure

theorem s180 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 → ENNReal.ofReal (1 - ξ) < 1 →
    Filter.Tendsto (fun n : ℕ => ENNReal.ofReal ((1 - ξ) ^ n)) Filter.atTop (nhds 0)  := by
  intro ξ hξ₁ hξ₂ h
  simp_rw [s180_sub_2 ξ hξ₁ hξ₂]
  exact s180_sub_3 ξ hξ₁ hξ₂ h

end Problems.cantor_xi_measure
