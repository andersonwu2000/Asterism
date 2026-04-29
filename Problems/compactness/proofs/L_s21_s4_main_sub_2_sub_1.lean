import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s21_s4_main_sub_2_sub_1 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    ∀ p : PropForm α, PropForm.neg p ∈ M → p ∉ M := by
  sorry

end Problems.compactness
