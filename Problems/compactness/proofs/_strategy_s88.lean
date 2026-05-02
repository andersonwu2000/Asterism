import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s88_sub_1
import Problems.compactness.proofs.L_s88_sub_2
import Problems.compactness.proofs.L_s88_sub_3

namespace Problems.compactness

theorem s88 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ (C : Set (Set (PropForm α))),
      C.Nonempty →
      IsChain (· ⊆ ·) C →
      (∀ X ∈ C, S ⊆ X ∧ (∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T)) →
      S ⊆ ⋃₀ C ∧ (∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T)) →
    ∃ M : Set (PropForm α),
      (S ⊆ M ∧ (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)) ∧
      ∀ N : Set (PropForm α),
        (S ⊆ N ∧ (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T)) →
        M ⊆ N → M = N := by
  intro α S h1 h2
  have hmemP : S ⊆ S ∧ ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T :=
    s88_sub_1 S h1
  have hchainUB :
      ∀ (C : Set (Set (PropForm α))),
        C ⊆ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T} →
        IsChain (· ⊆ ·) C →
        C.Nonempty →
        ∃ ub ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
          ∀ z ∈ C, z ⊆ ub :=
    s88_sub_2 S h2
  exact s88_sub_3 S hmemP hchainUB

end Problems.compactness
