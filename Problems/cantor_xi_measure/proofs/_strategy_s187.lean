import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s187_sub_1
import Problems.cantor_xi_measure.proofs.L_s187_sub_2
import Problems.cantor_xi_measure.proofs.L_s187_sub_3

namespace Problems.cantor_xi_measure

theorem s187 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ,
    MeasureTheory.volume ((fun x : ℝ => (1 + ξ) / 2 + (1 - ξ) / 2 * x) '' cantorXi ξ n) =
    ENNReal.ofReal ((1 - ξ) / 2) * MeasureTheory.volume (cantorXi ξ n)  := by
  intro ξ hξ0 hξ1 n
  have h1 : (fun x : ℝ => (1 + ξ) / 2 + (1 - ξ) / 2 * x) =
            ⇑(AffineMap.homothety (1 : ℝ) ((1 - ξ) / 2)) := by
    funext x
    exact s187_sub_1 ξ hξ0 hξ1 n x
  rw [h1]
  exact s187_sub_3 ξ hξ0 hξ1 n

end Problems.cantor_xi_measure
