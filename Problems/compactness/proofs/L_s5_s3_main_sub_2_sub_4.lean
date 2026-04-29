import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s5_s3_main_sub_2_sub_4 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α, p ∉ M → PropForm.neg p ∈ M := by
  sorry

end Problems.compactness
