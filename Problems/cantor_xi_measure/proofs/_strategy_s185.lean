import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s185_sub_1
import Problems.cantor_xi_measure.proofs.L_s185_sub_2
import Problems.cantor_xi_measure.proofs.L_s185_sub_3
import Problems.cantor_xi_measure.proofs.L_s185_sub_4
import Problems.cantor_xi_measure.proofs.L_s185_sub_5

namespace Problems.cantor_xi_measure

theorem s185 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ,
    MeasureTheory.volume (cantorXi ξ n) = ENNReal.ofReal ((1 - ξ) ^ n) →
    MeasureTheory.volume (cantorXi ξ (n + 1)) = ENNReal.ofReal ((1 - ξ) ^ (n + 1))  := by
  intro ξ hξ₁ hξ₂ n ih
  show MeasureTheory.volume (((fun x : ℝ => (1 - ξ) / 2 * x) '' cantorXi ξ n) ∪
      ((fun x : ℝ => (1 + ξ) / 2 + (1 - ξ) / 2 * x) '' cantorXi ξ n)) =
      ENNReal.ofReal ((1 - ξ) ^ (n + 1))
  have hc_n : IsCompact (cantorXi ξ n) := s185_sub_1 ξ hξ₁ hξ₂ n
  have hms_right : MeasurableSet ((fun x : ℝ => (1 + ξ) / 2 + (1 - ξ) / 2 * x) '' cantorXi ξ n) :=
    (hc_n.image (by fun_prop)).measurableSet
  have h_disj : Disjoint ((fun x : ℝ => (1 - ξ) / 2 * x) '' cantorXi ξ n)
      ((fun x : ℝ => (1 + ξ) / 2 + (1 - ξ) / 2 * x) '' cantorXi ξ n) :=
    s185_sub_4 ξ hξ₁ hξ₂ n
  rw [MeasureTheory.measure_union h_disj hms_right, s185_sub_2 ξ hξ₁ hξ₂ n,
      s185_sub_3 ξ hξ₁ hξ₂ n, ih]
  exact s185_sub_5 ξ hξ₁ hξ₂ n

end Problems.cantor_xi_measure
