import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s186_sub_1
import Problems.cantor_xi_measure.proofs.L_s186_sub_2

namespace Problems.cantor_xi_measure

open scoped Pointwise

theorem s186 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ,
    MeasureTheory.volume ((fun x : ℝ => (1 - ξ) / 2 * x) '' cantorXi ξ n) =
    ENNReal.ofReal ((1 - ξ) / 2) * MeasureTheory.volume (cantorXi ξ n)  := by
  intro ξ hξ hξ1 n
  have hr : (0 : ℝ) ≤ (1 - ξ) / 2 := by linarith
  have h2 := MeasureTheory.Measure.addHaar_smul_of_nonneg MeasureTheory.volume hr (cantorXi ξ n)
  rw [s186_sub_1 ξ hξ hξ1 n, h2, s186_sub_2 ξ hξ hξ1]

end Problems.cantor_xi_measure
