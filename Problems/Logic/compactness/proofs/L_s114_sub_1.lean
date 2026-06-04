import Mathlib
import Problems.Logic.compactness.Defs

namespace Problems.Logic.compactness

theorem s114_sub_1 : ∀ {α : Type} (C : Set (Set (PropForm α))),
    C.Nonempty →
    ∃ X ∈ C, (∅ : Set (PropForm α)) ⊆ X := by aesop

end Problems.Logic.compactness
