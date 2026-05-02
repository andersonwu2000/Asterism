import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s117_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    S ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T} →
    (∀ (C : Set (Set (PropForm α))),
      C ⊆ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T} →
      IsChain (· ⊆ ·) C →
      C.Nonempty →
      ∃ ub ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
        ∀ z ∈ C, z ⊆ ub) →
    ∃ M ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
      S ⊆ M ∧
      ∀ N ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
        M ⊆ N → N = M := by
  intro α S hS hch
  obtain ⟨M, hSM, hMmax⟩ := zorn_subset_nonempty _ hch S hS
  refine ⟨M, hMmax.1, hSM, fun N hN hMN => ?_⟩
  exact Set.Subset.antisymm (hMmax.2 hN hMN) hMN

end Problems.compactness
