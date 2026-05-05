import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s184_sub_1
import Problems.cantor_xi_measure.proofs.L_s184_sub_2

namespace Problems.cantor_xi_measure

theorem s184 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ, cantorXi ξ n ⊆ Set.Icc 0 1  := by
  intro ξ hξ₁ hξ₂ n
  induction n with
  | zero => simp [cantorXi]
  | succ n ih =>
    simp only [cantorXi]
    exact Set.union_subset
      (s184_sub_1 ξ hξ₁ hξ₂ (cantorXi ξ n) ih)
      (s184_sub_2 ξ hξ₁ hξ₂ (cantorXi ξ n) ih)

end Problems.cantor_xi_measure
