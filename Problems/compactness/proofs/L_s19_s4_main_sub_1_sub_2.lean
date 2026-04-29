import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s19_s4_main_sub_1_sub_2 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ (c : Set (Set (PropForm α))) (T : Set (PropForm α)),
      IsChain (· ⊆ ·) c → T.Finite → T ⊆ ⋃₀c → ∃ N ∈ c, T ⊆ N) →
    ∀ (c : Set (Set (PropForm α))),
      c ⊆ {N : Set (PropForm α) | S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T} →
      IsChain (· ⊆ ·) c →
      c.Nonempty →
      S ⊆ ⋃₀c ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀c → T.Finite → Sat T := by nlinarith

end Problems.compactness
