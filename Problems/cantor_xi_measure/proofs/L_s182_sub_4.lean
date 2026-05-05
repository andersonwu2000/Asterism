import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open Set

theorem s182_sub_4 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ, IsCompact (cantorXi ξ n) → IsCompact (cantorXi ξ (n + 1)) := by
  intro ξ _ _ n hn
  simp only [cantorXi]
  apply IsCompact.union
  · exact hn.image (by fun_prop)
  · exact hn.image (by fun_prop)

end Problems.cantor_xi_measure
