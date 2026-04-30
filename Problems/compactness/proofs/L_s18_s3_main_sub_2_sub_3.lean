import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s18_s3_main_sub_2_sub_3 : ∀ {α : Type} (M : Set (PropForm α)) (p : PropForm α),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∃ T₀ : Set (PropForm α), T₀ ⊆ M ∧ T₀.Finite ∧ ¬Sat (T₀ ∪ {p})) →
    (∃ T₁ : Set (PropForm α), T₁ ⊆ M ∧ T₁.Finite ∧ ¬Sat (T₁ ∪ {PropForm.neg p})) →
    False := by
  sorry

end Problems.compactness
