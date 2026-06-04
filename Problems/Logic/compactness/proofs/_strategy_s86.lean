import Mathlib
import Problems.Logic.compactness.Defs
import Problems.Logic.compactness.proofs.L_s86_sub_1
import Problems.Logic.compactness.proofs.L_s86_sub_2
import Problems.Logic.compactness.proofs.L_s86_sub_3

namespace Problems.Logic.compactness

theorem s86 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ (C : Set (Set (PropForm α))),
      C.Nonempty →
      IsChain (· ⊆ ·) C →
      (∀ X ∈ C, ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T) →
      ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T) →
    ∃ M : Set (PropForm α),
      S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α), M ⊆ N →
        (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N := by
  intro α S h1 h2
  have hchain : ∀ (C : Set (Set (PropForm α))),
      C.Nonempty →
      IsChain (· ⊆ ·) C →
      (∀ X ∈ C, S ⊆ X ∧ (∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T)) →
      S ⊆ ⋃₀ C ∧ (∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T) :=
    s86_sub_1 S h2
  have hzorn : ∃ M : Set (PropForm α),
      (S ⊆ M ∧ (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)) ∧
      ∀ N : Set (PropForm α),
        (S ⊆ N ∧ (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T)) →
        M ⊆ N → M = N :=
    s86_sub_2 S h1 hchain
  exact s86_sub_3 S hzorn

end Problems.Logic.compactness
