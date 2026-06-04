import Mathlib
import Problems.Logic.compactness.Defs

namespace Problems.Logic.compactness

theorem s115_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (S ⊆ S ∧ ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    S ⊆ S := by norm_num

end Problems.Logic.compactness
