import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s115_sub_2 : ∀ {α : Type} (S : Set (PropForm α)),
    (S ⊆ S ∧ ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T := by norm_num

end Problems.compactness
