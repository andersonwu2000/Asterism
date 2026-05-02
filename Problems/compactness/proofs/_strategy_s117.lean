import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s117_sub_1
import Problems.compactness.proofs.L_s117_sub_2

namespace Problems.compactness

theorem s117 : ∀ {α : Type} (S : Set (PropForm α)),
    S ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T} →
    (∀ (C : Set (Set (PropForm α))),
      C ⊆ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T} →
      IsChain (· ⊆ ·) C →
      C.Nonempty →
      ∃ ub ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
        ∀ z ∈ C, z ⊆ ub) →
    ∃ M ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
      ∀ N ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
        M ⊆ N → N = M := by
  intro α S hS hch
  have hstrong :
      ∃ M ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
        S ⊆ M ∧
        ∀ N ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
          M ⊆ N → N = M :=
    s117_sub_1 S hS hch
  exact s117_sub_2 S hS hch hstrong

end Problems.compactness
