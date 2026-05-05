import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s171_sub_1
import Problems.cantor_xi_measure.proofs.L_s171_sub_2
import Problems.cantor_xi_measure.proofs.L_s171_sub_3
import Problems.cantor_xi_measure.proofs.L_s171_sub_4

namespace Problems.cantor_xi_measure

theorem s171 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ, MeasureTheory.volume (cantorXi ξ n) = ENNReal.ofReal ((1 - ξ) ^ n)  := by
  intro ξ hξ₁ hξ₂ n
  induction n with
  | zero =>
    simp [cantorXi, Real.volume_Icc]
  | succ n ih =>
    exact s171_sub_4 ξ hξ₁ hξ₂ n ih

end Problems.cantor_xi_measure
