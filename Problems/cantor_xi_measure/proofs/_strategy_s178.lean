import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s178_sub_1
import Problems.cantor_xi_measure.proofs.L_s178_sub_2

namespace Problems.cantor_xi_measure

theorem s178 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    (∀ n : ℕ, MeasureTheory.volume (cantorXi ξ n) = ENNReal.ofReal ((1 - ξ) ^ n)) →
    (∀ n : ℕ, cantorSet ξ ⊆ cantorXi ξ n) →
    (∀ n : ℕ, MeasureTheory.volume (cantorSet ξ) ≤ MeasureTheory.volume (cantorXi ξ n)) →
    ∀ n : ℕ, MeasureTheory.volume (cantorSet ξ) ≤ ENNReal.ofReal ((1 - ξ) ^ n)  := by
  intro ξ hξ₁ hξ₂ h1 h2 h3
  exact s178_sub_2
    (fun n => MeasureTheory.volume (cantorXi ξ n))
    (fun n => ENNReal.ofReal ((1 - ξ) ^ n))
    (MeasureTheory.volume (cantorSet ξ))
    h3 h1 s178_sub_1

end Problems.cantor_xi_measure
