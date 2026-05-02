import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s91_sub_1
import Problems.compactness.proofs.L_s91_sub_2
import Problems.compactness.proofs.L_s91_sub_3

namespace Problems.compactness

theorem s91 : ∀ {α : Type} (S : Set (PropForm α)),
    (S ⊆ S ∧ ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ (C : Set (Set (PropForm α))),
      C ⊆ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T} →
      IsChain (· ⊆ ·) C →
      C.Nonempty →
      ∃ ub ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
        ∀ z ∈ C, z ⊆ ub) →
    ∃ M : Set (PropForm α),
      (S ⊆ M ∧ ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α),
        (S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
        M ⊆ N → M = N := by
  intro α S h1 h2
  have hSP : S ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T} :=
    s91_sub_1 S h1
  have hzorn : ∃ M ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
      ∀ N ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
        M ⊆ N → N = M :=
    s91_sub_2 S hSP h2
  exact s91_sub_3 S hzorn

end Problems.compactness
