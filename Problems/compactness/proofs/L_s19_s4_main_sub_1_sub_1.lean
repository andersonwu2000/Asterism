import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s19_s4_main_sub_1_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∀ (c : Set (Set (PropForm α))) (T : Set (PropForm α)),
      IsChain (· ⊆ ·) c →
      T.Finite →
      T ⊆ ⋃₀c →
      ∃ N ∈ c, T ⊆ N := by norm_num

end Problems.compactness
