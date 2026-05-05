import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open Set MeasureTheory

/-- Every iterate of the ξ-Cantor construction is compact. -/
theorem s185_sub_1 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ, IsCompact (cantorXi ξ n) := by
  intro ξ _ _ n
  induction n with
  | zero => exact isCompact_Icc
  | succ n ih =>
    simp only [cantorXi]
    exact (ih.image (by fun_prop)).union (ih.image (by fun_prop))

end Problems.cantor_xi_measure
