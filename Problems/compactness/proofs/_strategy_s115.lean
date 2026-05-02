import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s115_sub_1
import Problems.compactness.proofs.L_s115_sub_2

namespace Problems.compactness

theorem s115 : ∀ {α : Type} (S : Set (PropForm α)),
    (S ⊆ S ∧ ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    S ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T} := by
  intro α S h1
  have h_sub : S ⊆ S := s115_sub_1 S h1
  have h_finsat : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T := s115_sub_2 S h1
  exact ⟨h_sub, h_finsat⟩

end Problems.compactness
