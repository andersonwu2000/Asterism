import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s114_sub_1 : ∀ {α : Type} (C : Set (Set (PropForm α))),
    C.Nonempty →
    ∃ X ∈ C, (∅ : Set (PropForm α)) ⊆ X := by aesop

end Problems.compactness
