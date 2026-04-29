import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s19_s4_main_sub_1_sub_3 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ (c : Set (Set (PropForm α))),
      c ⊆ {N : Set (PropForm α) | S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T} →
      IsChain (· ⊆ ·) c →
      c.Nonempty →
      ∃ ub ∈ {N : Set (PropForm α) | S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T},
        ∀ z ∈ c, z ⊆ ub) →
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ M' : Set (PropForm α), M ⊆ M' →
        (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M = M' := by omega

end Problems.compactness
