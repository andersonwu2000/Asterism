import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s182_sub_1
import Problems.cantor_xi_measure.proofs.L_s182_sub_2
import Problems.cantor_xi_measure.proofs.L_s182_sub_3
import Problems.cantor_xi_measure.proofs.L_s182_sub_4

namespace Problems.cantor_xi_measure

theorem s182 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ, IsCompact (cantorXi ξ n)  := by
  intro ξ hξ₁ hξ₂ n
  induction n with
  | zero => exact s182_sub_1 ξ hξ₁ hξ₂
  | succ n ih => exact s182_sub_4 ξ hξ₁ hξ₂ n ih

end Problems.cantor_xi_measure
