import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open Set

theorem s182_sub_1 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    IsCompact (cantorXi ξ 0) := by
  intro ξ _ _
  exact isCompact_Icc

end Problems.cantor_xi_measure
